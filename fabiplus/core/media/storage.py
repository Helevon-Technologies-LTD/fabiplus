"""
File storage backends for FABI+ media system
Supports local storage, cloud storage (S3, GCS, Azure), and custom backends
"""

import hashlib
import mimetypes
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional, Tuple

from pydantic import BaseModel


class StorageConfig(BaseModel):
    """Configuration for storage backends"""

    backend: str = "local"
    base_path: str = "media"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    allowed_extensions: List[str] = [
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".pdf",
        ".txt",
        ".doc",
        ".docx",
    ]
    create_thumbnails: bool = True
    thumbnail_sizes: List[Tuple[int, int]] = [(150, 150), (300, 300)]


class FileMetadata(BaseModel):
    """File metadata information"""

    filename: str
    original_filename: str
    size: int
    content_type: str
    extension: str
    hash_md5: str
    hash_sha256: str
    upload_date: datetime
    path: str
    url: str
    thumbnails: Dict[str, str] = {}


class FileStorage(ABC):
    """Abstract base class for file storage backends"""

    def __init__(self, config: StorageConfig):
        self.config = config

    @abstractmethod
    async def save(
        self, file: BinaryIO, filename: str, folder: str = ""
    ) -> FileMetadata:
        """Save a file and return metadata"""
        pass

    @abstractmethod
    async def delete(self, path: str) -> bool:
        """Delete a file"""
        pass

    @abstractmethod
    async def exists(self, path: str) -> bool:
        """Check if file exists"""
        pass

    @abstractmethod
    async def get_url(self, path: str, expires_in: Optional[int] = None) -> str:
        """Get URL for file access"""
        pass

    @abstractmethod
    async def get_metadata(self, path: str) -> Optional[FileMetadata]:
        """Get file metadata"""
        pass

    @abstractmethod
    async def list_files(
        self, folder: str = "", limit: int = 100, offset: int = 0
    ) -> List[FileMetadata]:
        """List files in folder"""
        pass

    def _generate_filename(self, original_filename: str) -> str:
        """Generate unique filename"""
        ext = Path(original_filename).suffix.lower()
        unique_id = str(uuid.uuid4())
        return f"{unique_id}{ext}"

    def _calculate_hashes(self, content: bytes) -> Tuple[str, str]:
        """Calculate MD5 and SHA256 hashes"""
        md5_hash = hashlib.md5(content).hexdigest()
        sha256_hash = hashlib.sha256(content).hexdigest()
        return md5_hash, sha256_hash

    def _get_content_type(self, filename: str) -> str:
        """Get content type from filename"""
        content_type, _ = mimetypes.guess_type(filename)
        return content_type or "application/octet-stream"


class LocalFileStorage(FileStorage):
    """Local filesystem storage backend"""

    def __init__(self, config: StorageConfig):
        super().__init__(config)
        self.base_path = Path(config.base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    async def save(
        self, file: BinaryIO, filename: str, folder: str = ""
    ) -> FileMetadata:
        """Save file to local filesystem"""

        # Read file content
        content = file.read()
        file.seek(0)  # Reset file pointer

        # Validate file size
        if len(content) > self.config.max_file_size:
            raise ValueError(
                f"File size exceeds maximum allowed size of {self.config.max_file_size} bytes"
            )

        # Validate file extension
        ext = Path(filename).suffix.lower()
        if ext not in self.config.allowed_extensions:
            raise ValueError(f"File extension {ext} not allowed")

        # Generate unique filename
        unique_filename = self._generate_filename(filename)

        # Create folder path
        folder_path = self.base_path / folder if folder else self.base_path
        folder_path.mkdir(parents=True, exist_ok=True)

        # Save file
        file_path = folder_path / unique_filename
        with open(file_path, "wb") as f:
            f.write(content)

        # Calculate hashes
        md5_hash, sha256_hash = self._calculate_hashes(content)

        # Create metadata
        relative_path = str(file_path.relative_to(self.base_path))
        metadata = FileMetadata(
            filename=unique_filename,
            original_filename=filename,
            size=len(content),
            content_type=self._get_content_type(filename),
            extension=ext,
            hash_md5=md5_hash,
            hash_sha256=sha256_hash,
            upload_date=datetime.now(),
            path=relative_path,
            url=f"/media/{relative_path}",
        )

        return metadata

    async def delete(self, path: str) -> bool:
        """Delete file from local filesystem"""
        file_path = self.base_path / path
        try:
            if file_path.exists():
                file_path.unlink()
                return True
            return False
        except Exception:
            return False

    async def exists(self, path: str) -> bool:
        """Check if file exists"""
        file_path = self.base_path / path
        return file_path.exists()

    async def get_url(self, path: str, expires_in: Optional[int] = None) -> str:
        """Get URL for file access"""
        return f"/media/{path}"

    async def get_metadata(self, path: str) -> Optional[FileMetadata]:
        """Get file metadata"""
        file_path = self.base_path / path

        if not file_path.exists():
            return None

        stat = file_path.stat()

        # Read file to calculate hashes
        with open(file_path, "rb") as f:
            content = f.read()

        md5_hash, sha256_hash = self._calculate_hashes(content)

        return FileMetadata(
            filename=file_path.name,
            original_filename=file_path.name,
            size=stat.st_size,
            content_type=self._get_content_type(file_path.name),
            extension=file_path.suffix.lower(),
            hash_md5=md5_hash,
            hash_sha256=sha256_hash,
            upload_date=datetime.fromtimestamp(stat.st_mtime),
            path=path,
            url=f"/media/{path}",
        )

    async def list_files(
        self, folder: str = "", limit: int = 100, offset: int = 0
    ) -> List[FileMetadata]:
        """List files in folder"""
        folder_path = self.base_path / folder if folder else self.base_path

        if not folder_path.exists():
            return []

        files = []
        for file_path in folder_path.rglob("*"):
            if file_path.is_file():
                relative_path = str(file_path.relative_to(self.base_path))
                metadata = await self.get_metadata(relative_path)
                if metadata:
                    files.append(metadata)

        # Apply pagination
        return files[offset : offset + limit]


class CloudFileStorage(FileStorage):
    """Cloud storage backend (S3, GCS, Azure)"""

    def __init__(self, config: StorageConfig, cloud_config: Dict[str, Any]):
        super().__init__(config)
        self.cloud_config = cloud_config
        self.provider = cloud_config.get("provider", "s3")

        # Initialize cloud client based on provider
        if self.provider == "s3":
            self._init_s3_client()
        elif self.provider == "gcs":
            self._init_gcs_client()
        elif self.provider == "azure":
            self._init_azure_client()
        else:
            raise ValueError(f"Unsupported cloud provider: {self.provider}")

    def _init_s3_client(self):
        """Initialize S3 client"""
        try:
            import boto3

            self.client = boto3.client(
                "s3",
                aws_access_key_id=self.cloud_config.get("access_key"),
                aws_secret_access_key=self.cloud_config.get("secret_key"),
                region_name=self.cloud_config.get("region", "us-east-1"),
            )
            self.bucket = self.cloud_config.get("bucket")
        except ImportError:
            raise ImportError(
                "boto3 is required for S3 storage. Install with: pip install boto3"
            )

    def _init_gcs_client(self):
        """Initialize Google Cloud Storage client"""
        try:
            from google.cloud import storage

            self.client = storage.Client()
            self.bucket = self.client.bucket(self.cloud_config.get("bucket"))
        except ImportError:
            raise ImportError(
                "google-cloud-storage is required for GCS. Install with: pip install google-cloud-storage"
            )

    def _init_azure_client(self):
        """Initialize Azure Blob Storage client"""
        try:
            from azure.storage.blob import BlobServiceClient

            self.client = BlobServiceClient(
                account_url=self.cloud_config.get("account_url"),
                credential=self.cloud_config.get("credential"),
            )
            self.container = self.cloud_config.get("container")
        except ImportError:
            raise ImportError(
                "azure-storage-blob is required for Azure storage. Install with: pip install azure-storage-blob"
            )

    async def save(
        self, file: BinaryIO, filename: str, folder: str = ""
    ) -> FileMetadata:
        """Save file to cloud storage"""
        # Implementation depends on cloud provider
        # This is a placeholder - would need specific implementation for each provider
        raise NotImplementedError("Cloud storage save not yet implemented")

    async def delete(self, path: str) -> bool:
        """Delete file from cloud storage"""
        raise NotImplementedError("Cloud storage delete not yet implemented")

    async def exists(self, path: str) -> bool:
        """Check if file exists in cloud storage"""
        raise NotImplementedError("Cloud storage exists not yet implemented")

    async def get_url(self, path: str, expires_in: Optional[int] = None) -> str:
        """Get URL for file access"""
        raise NotImplementedError("Cloud storage get_url not yet implemented")

    async def get_metadata(self, path: str) -> Optional[FileMetadata]:
        """Get file metadata from cloud storage"""
        raise NotImplementedError("Cloud storage get_metadata not yet implemented")

    async def list_files(
        self, folder: str = "", limit: int = 100, offset: int = 0
    ) -> List[FileMetadata]:
        """List files in cloud storage folder"""
        raise NotImplementedError("Cloud storage list_files not yet implemented")
