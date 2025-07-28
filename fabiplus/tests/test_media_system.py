"""
Tests for FABI+ Media System
Tests file upload, storage, validation, processing, and serving
"""

import shutil
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from fabiplus.core.media.handlers import FileDownloadHandler, FileUploadHandler
from fabiplus.core.media.models import MediaFile, MediaFolder
from fabiplus.core.media.processors import FileProcessor, ImageProcessor
from fabiplus.core.media.storage import FileMetadata, LocalFileStorage, StorageConfig
from fabiplus.core.media.validators import (
    DocumentValidator,
    FileValidator,
    ImageValidator,
)


class TestFileStorage:
    """Test file storage backends"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = StorageConfig(base_path=str(self.temp_dir))
        self.storage = LocalFileStorage(self.config)

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_storage_initialization(self):
        """Test storage backend initialization"""
        assert self.storage.config.base_path == str(self.temp_dir)
        assert self.temp_dir.exists()

    async def test_file_save_and_retrieve(self):
        """Test saving and retrieving files"""
        # Create test file
        test_content = b"Hello, World!"
        test_file = BytesIO(test_content)

        # Save file
        metadata = await self.storage.save(test_file, "test.txt")

        assert isinstance(metadata, FileMetadata)
        assert metadata.original_filename == "test.txt"
        assert metadata.size == len(test_content)
        assert metadata.content_type == "text/plain"

        # Check file exists
        assert await self.storage.exists(metadata.path)

        # Get metadata
        retrieved_metadata = await self.storage.get_metadata(metadata.path)
        assert retrieved_metadata is not None
        assert retrieved_metadata.size == metadata.size

    async def test_file_deletion(self):
        """Test file deletion"""
        # Create and save test file
        test_file = BytesIO(b"Test content")
        metadata = await self.storage.save(test_file, "delete_test.txt")

        # Verify file exists
        assert await self.storage.exists(metadata.path)

        # Delete file
        deleted = await self.storage.delete(metadata.path)
        assert deleted is True

        # Verify file no longer exists
        assert not await self.storage.exists(metadata.path)

    async def test_file_listing(self):
        """Test listing files in storage"""
        # Create multiple test files
        for i in range(3):
            test_file = BytesIO(f"Content {i}".encode())
            await self.storage.save(test_file, f"test_{i}.txt")

        # List files
        files = await self.storage.list_files()
        assert len(files) == 3

        # Test pagination
        files_page1 = await self.storage.list_files(limit=2, offset=0)
        assert len(files_page1) == 2

        files_page2 = await self.storage.list_files(limit=2, offset=2)
        assert len(files_page2) == 1


class TestFileValidators:
    """Test file validation system"""

    def test_basic_file_validator(self):
        """Test basic file validator"""
        validator = FileValidator(max_file_size=1024)

        assert validator.max_file_size == 1024
        assert ".jpg" in validator.allowed_extensions

    async def test_file_size_validation(self):
        """Test file size validation"""
        validator = FileValidator(max_file_size=100)

        # Create mock upload file
        large_content = b"x" * 200
        mock_file = MagicMock()
        mock_file.filename = "large.txt"
        mock_file.read.return_value = large_content
        mock_file.seek = MagicMock()

        # Should raise HTTPException for large file
        with pytest.raises(HTTPException):
            await validator.validate(mock_file)

    async def test_extension_validation(self):
        """Test file extension validation"""
        validator = FileValidator(allowed_extensions={".txt", ".pdf"})

        # Valid extension
        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.read.return_value = b"small content"
        mock_file.seek = MagicMock()

        # Should not raise exception
        result = await validator.validate(mock_file)
        assert result["valid"] is True

    def test_image_validator_initialization(self):
        """Test image validator initialization"""
        validator = ImageValidator(max_width=1920, max_height=1080)

        assert validator.max_width == 1920
        assert validator.max_height == 1080
        assert ".jpg" in validator.allowed_extensions
        assert "image/jpeg" in validator.allowed_mime_types

    def test_document_validator_initialization(self):
        """Test document validator initialization"""
        validator = DocumentValidator()

        assert ".pdf" in validator.allowed_extensions
        assert "application/pdf" in validator.allowed_mime_types


class TestFileProcessors:
    """Test file processing system"""

    def test_file_processor_initialization(self):
        """Test file processor initialization"""
        config = {"thumbnail_sizes": [(100, 100), (200, 200)]}
        processor = FileProcessor(config)

        assert processor.thumbnail_sizes == [(100, 100), (200, 200)]

    async def test_image_processing(self):
        """Test image processing"""
        processor = ImageProcessor()

        # Create test image
        image = Image.new("RGB", (800, 600), color="red")
        image_buffer = BytesIO()
        image.save(image_buffer, format="JPEG")
        image_content = image_buffer.getvalue()

        # Create mock metadata
        metadata = FileMetadata(
            filename="test.jpg",
            original_filename="test.jpg",
            size=len(image_content),
            content_type="image/jpeg",
            extension=".jpg",
            hash_md5="test_md5",
            hash_sha256="test_sha256",
            upload_date="2023-01-01T00:00:00",
            path="test.jpg",
            url="/media/test.jpg",
        )

        # Process image
        result = await processor.process(image_content, metadata)

        assert "width" in result
        assert "height" in result
        assert result["width"] == 800
        assert result["height"] == 600
        assert "thumbnails" in result


class TestFileHandlers:
    """Test file upload and download handlers"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config = StorageConfig(base_path=str(self.temp_dir))
        self.storage = LocalFileStorage(self.config)
        self.validator = FileValidator()
        self.processor = FileProcessor()
        self.upload_handler = FileUploadHandler(
            self.storage, self.validator, self.processor
        )
        self.download_handler = FileDownloadHandler(self.storage)

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    async def test_single_file_upload(self):
        """Test uploading a single file"""
        # Create mock upload file
        test_content = b"Test file content"
        mock_file = MagicMock()
        mock_file.filename = "test.txt"
        mock_file.file = BytesIO(test_content)
        mock_file.read.return_value = test_content
        mock_file.seek = MagicMock()

        # Mock session
        mock_session = MagicMock()

        # Upload file
        media_file = await self.upload_handler.upload_single_file(
            file=mock_file,
            title="Test File",
            description="Test Description",
            session=mock_session,
        )

        assert media_file.original_filename == "test.txt"
        assert media_file.title == "Test File"
        assert media_file.description == "Test Description"
        assert media_file.size == len(test_content)

    async def test_chunked_upload_session(self):
        """Test chunked upload session creation"""
        mock_session = MagicMock()

        upload_session = await self.upload_handler.start_chunked_upload(
            filename="large_file.txt",
            total_size=1000,
            chunk_size=100,
            session=mock_session,
        )

        assert upload_session.filename == "large_file.txt"
        assert upload_session.total_size == 1000
        assert upload_session.chunk_size == 100
        assert upload_session.total_chunks == 10


class TestMediaModels:
    """Test media database models"""

    def test_media_file_model(self):
        """Test MediaFile model"""
        media_file = MediaFile(
            filename="test.jpg",
            original_filename="original.jpg",
            title="Test Image",
            size=1024,
            content_type="image/jpeg",
            extension=".jpg",
            storage_backend="local",
            storage_path="test.jpg",
            storage_url="/media/test.jpg",
            hash_md5="test_md5",
            hash_sha256="test_sha256",
        )

        assert media_file.is_image is True
        assert media_file.is_video is False
        assert media_file.is_audio is False
        assert media_file.is_document is False

    def test_media_folder_model(self):
        """Test MediaFolder model"""
        folder = MediaFolder(name="Test Folder", description="Test folder description")

        assert folder.name == "Test Folder"
        assert folder.slug == "test-folder"  # Auto-generated slug
        assert folder.description == "Test folder description"

    def test_media_file_properties(self):
        """Test MediaFile computed properties"""
        # Test video file
        video_file = MediaFile(
            filename="video.mp4",
            original_filename="video.mp4",
            content_type="video/mp4",
            size=1024 * 1024,  # 1MB
            extension=".mp4",
            storage_backend="local",
            storage_path="video.mp4",
            storage_url="/media/video.mp4",
            hash_md5="test_md5",
            hash_sha256="test_sha256",
        )

        assert video_file.is_video is True
        assert video_file.is_image is False

        # Test PDF file
        pdf_file = MediaFile(
            filename="doc.pdf",
            original_filename="doc.pdf",
            content_type="application/pdf",
            size=2048,
            extension=".pdf",
            storage_backend="local",
            storage_path="doc.pdf",
            storage_url="/media/doc.pdf",
            hash_md5="test_md5",
            hash_sha256="test_sha256",
        )

        assert pdf_file.is_document is True
        assert pdf_file.is_image is False


class TestMediaAPI:
    """Test media API endpoints"""

    def setup_method(self):
        """Setup test environment"""
        # This would require setting up a test FastAPI app
        # For now, just test the basic structure
        pass

    def test_upload_endpoint_structure(self):
        """Test upload endpoint structure"""
        # This would test the actual API endpoints
        # Requires FastAPI test client setup
        pass

    def test_download_endpoint_structure(self):
        """Test download endpoint structure"""
        # This would test the actual API endpoints
        # Requires FastAPI test client setup
        pass


class TestMediaIntegration:
    """Integration tests for media system"""

    def setup_method(self):
        """Setup test environment"""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Cleanup test environment"""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    async def test_full_upload_workflow(self):
        """Test complete file upload workflow"""
        # This would test the entire workflow:
        # 1. File validation
        # 2. File processing
        # 3. Storage
        # 4. Database record creation
        # 5. Response generation
        pass

    async def test_full_download_workflow(self):
        """Test complete file download workflow"""
        # This would test the entire workflow:
        # 1. File lookup
        # 2. Permission checking
        # 3. File serving
        # 4. Access logging
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
