"""
Database models for media and file management
"""

import json
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional


from sqlalchemy import Text
from sqlmodel import JSON, Column, Field, Relationship, SQLModel


class MediaFolder(SQLModel, table=True):
    """Model for organizing media files in folders"""

    __tablename__ = "media_folders"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=255, description="Folder name")
    slug: Optional[str] = Field(
        default=None, max_length=255, unique=True, description="URL-friendly folder name"
    )
    description: Optional[str] = Field(default="", description="Folder description")
    parent_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="media_folders.id", description="Parent folder"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[uuid.UUID] = Field(
        default=None, description="User who created the folder"
    )

    # Relationships
    parent_id: Optional[uuid.UUID] = Field(default=None, foreign_key="media_folders.id")
    parent: Optional["MediaFolder"] = Relationship(
        back_populates="children",
        sa_relationship_kwargs={"remote_side": "MediaFolder.id"},
    )
    children: List["MediaFolder"] = Relationship(back_populates="parent")
    files: List["MediaFile"] = Relationship(back_populates="folder")

    # Configuration
    is_public: bool = Field(
        default=True, description="Whether folder is publicly accessible"
    )
    max_file_size: Optional[int] = Field(
        default=None, description="Maximum file size for this folder"
    )
    allowed_extensions: Optional[str] = Field(
        default=None, description="JSON string of allowed file extensions"
    )

    class Config:
        _verbose_name = "Media Folder"
        _verbose_name_plural = "Media Folders"

    def __str__(self):
        return self.name

    def __init__(self, **data):
        # Auto-generate slug if not provided
        if not data.get("slug") and data.get("name"):
            import re
            slug = re.sub(r"[^a-zA-Z0-9\-_]", "-", data["name"].lower())
            slug = re.sub(r"-+", "-", slug).strip("-")
            data["slug"] = slug
        super().__init__(**data)


class MediaFile(SQLModel, table=True):
    """Model for storing media file information"""

    __tablename__ = "media_files"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # File information
    filename: str = Field(max_length=255, description="Generated filename")
    original_filename: str = Field(
        max_length=255, description="Original uploaded filename"
    )
    title: Optional[str] = Field(
        default="", max_length=255, description="Display title"
    )
    description: Optional[str] = Field(default="", description="File description")
    alt_text: Optional[str] = Field(
        default="", max_length=255, description="Alt text for images"
    )

    # File metadata
    size: int = Field(description="File size in bytes")
    content_type: str = Field(max_length=100, description="MIME content type")
    extension: str = Field(max_length=10, description="File extension")

    # Storage information
    storage_backend: str = Field(
        default="local", max_length=50, description="Storage backend used"
    )
    storage_path: str = Field(max_length=500, description="Path in storage backend")
    storage_url: str = Field(max_length=500, description="Public URL for file access")

    # Security and integrity
    hash_md5: str = Field(max_length=32, description="MD5 hash of file content")
    hash_sha256: str = Field(max_length=64, description="SHA256 hash of file content")

    # Organization
    folder_id: Optional[uuid.UUID] = Field(default=None, foreign_key="media_folders.id")
    tags: Optional[str] = Field(
        default="[]", description="JSON string of file tags for organization"
    )

    # Access control
    is_public: bool = Field(
        default=True, description="Whether file is publicly accessible"
    )
    access_permissions: Optional[str] = Field(
        default="{}", description="JSON string of custom access permissions"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    uploaded_by: Optional[uuid.UUID] = Field(
        default=None, description="User who uploaded the file"
    )

    # Media-specific metadata
    width: Optional[int] = Field(default=None, description="Image/video width")
    height: Optional[int] = Field(default=None, description="Image/video height")
    duration: Optional[float] = Field(
        default=None, description="Audio/video duration in seconds"
    )

    # Thumbnails and variants
    thumbnails: Optional[str] = Field(
        default="{}", description="JSON string of thumbnail URLs by size"
    )
    variants: Optional[str] = Field(
        default="{}", description="JSON string of file variants (compressed, etc.)"
    )

    # Usage tracking
    download_count: int = Field(
        default=0, description="Number of times file was downloaded"
    )
    last_accessed: Optional[datetime] = Field(
        default=None, description="Last access time"
    )

    # Relationships
    folder: Optional[MediaFolder] = Relationship(back_populates="files")

    class Config:
        _verbose_name = "Media File"
        _verbose_name_plural = "Media Files"

    def __str__(self):
        return self.title or self.original_filename

    @property
    def is_image(self) -> bool:
        """Check if file is an image"""
        return self.content_type.startswith("image/")

    @property
    def is_video(self) -> bool:
        """Check if file is a video"""
        return self.content_type.startswith("video/")

    @property
    def is_audio(self) -> bool:
        """Check if file is audio"""
        return self.content_type.startswith("audio/")

    @property
    def is_document(self) -> bool:
        """Check if file is a document"""
        document_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "text/plain",
            "text/csv",
        ]
        return self.content_type in document_types

    @property
    def human_readable_size(self) -> str:
        """Get human-readable file size"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if self.size < 1024.0:
                return f"{self.size:.1f} {unit}"
            self.size /= 1024.0
        return f"{self.size:.1f} PB"

    def get_thumbnail_url(self, size: str = "medium") -> Optional[str]:
        """Get thumbnail URL for specific size"""
        return self.thumbnails.get(size)

    def increment_download_count(self):
        """Increment download counter"""
        self.download_count += 1
        self.last_accessed = datetime.now()


class MediaUploadSession(SQLModel, table=True):
    """Model for tracking file upload sessions (for chunked uploads)"""

    __tablename__ = "media_upload_sessions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    session_id: str = Field(
        max_length=100, unique=True, description="Unique session identifier"
    )

    # File information
    filename: str = Field(max_length=255, description="Target filename")
    total_size: int = Field(description="Total file size")
    chunk_size: int = Field(description="Size of each chunk")
    total_chunks: int = Field(description="Total number of chunks")
    uploaded_chunks: Optional[str] = Field(
        default="[]", description="JSON string of uploaded chunk numbers"
    )

    # Session metadata
    created_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(description="Session expiration time")
    uploaded_by: Optional[uuid.UUID] = Field(
        default=None, description="User uploading the file"
    )

    # Storage information
    temp_storage_path: str = Field(max_length=500, description="Temporary storage path")
    target_folder_id: Optional[uuid.UUID] = Field(
        default=None, foreign_key="media_folders.id"
    )

    # Status
    is_complete: bool = Field(default=False, description="Whether upload is complete")
    is_cancelled: bool = Field(
        default=False, description="Whether upload was cancelled"
    )

    class Config:
        _verbose_name = "Upload Session"
        _verbose_name_plural = "Upload Sessions"

    def __str__(self):
        return f"Upload session for {self.filename}"

    @property
    def progress_percentage(self) -> float:
        """Get upload progress as percentage"""
        if self.total_chunks == 0:
            return 0.0
        return (len(self.uploaded_chunks) / self.total_chunks) * 100

    @property
    def is_expired(self) -> bool:
        """Check if session is expired"""
        return datetime.now() > self.expires_at

    def add_chunk(self, chunk_number: int):
        """Mark a chunk as uploaded"""
        if chunk_number not in self.uploaded_chunks:
            self.uploaded_chunks.append(chunk_number)
            self.uploaded_chunks.sort()

        # Check if upload is complete
        if len(self.uploaded_chunks) == self.total_chunks:
            self.is_complete = True
