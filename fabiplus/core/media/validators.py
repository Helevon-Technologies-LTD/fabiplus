"""
File validation system for FABI+ media uploads
"""

import mimetypes
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import magic
import pypdf
from fastapi import HTTPException, UploadFile, status
from PIL import Image


class ValidationError(Exception):
    """Custom exception for file validation errors"""

    pass


class FileValidator:
    """Base file validator with common validation rules"""

    def __init__(
        self,
        max_file_size: int = 10 * 1024 * 1024,  # 10MB
        allowed_extensions: Optional[Set[str]] = None,
        allowed_mime_types: Optional[Set[str]] = None,
        check_content: bool = True,
    ):
        self.max_file_size = max_file_size
        self.allowed_extensions = allowed_extensions or {
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".bmp",
            ".webp",  # Images
            ".pdf",
            ".doc",
            ".docx",
            ".txt",
            ".rtf",  # Documents
            ".mp4",
            ".avi",
            ".mov",
            ".wmv",
            ".flv",  # Videos
            ".mp3",
            ".wav",
            ".flac",
            ".aac",
            ".ogg",  # Audio
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",  # Archives
        }
        self.allowed_mime_types = allowed_mime_types
        self.check_content = check_content

    async def validate(self, file: UploadFile) -> Dict[str, Any]:
        """Validate uploaded file"""

        validation_result = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "metadata": {},
        }

        try:
            # Read file content for validation
            content = await file.read()
            await file.seek(0)  # Reset file pointer

            # Validate file size
            await self._validate_file_size(len(content), validation_result)

            # Validate file extension
            await self._validate_extension(file.filename, validation_result)

            # Validate MIME type
            if self.check_content:
                await self._validate_mime_type(
                    content, file.filename, validation_result
                )

            # Additional content validation
            await self._validate_content(content, file.filename, validation_result)

        except Exception as e:
            validation_result["valid"] = False
            validation_result["errors"].append(f"Validation error: {str(e)}")

        # Raise exception if validation failed
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "File validation failed",
                    "errors": validation_result["errors"],
                    "warnings": validation_result["warnings"],
                },
            )

        return validation_result

    async def _validate_file_size(self, size: int, result: Dict[str, Any]):
        """Validate file size"""
        if size > self.max_file_size:
            result["valid"] = False
            result["errors"].append(
                f"File size ({size} bytes) exceeds maximum allowed size ({self.max_file_size} bytes)"
            )

        result["metadata"]["size"] = size

    async def _validate_extension(self, filename: str, result: Dict[str, Any]):
        """Validate file extension"""
        if not filename:
            result["valid"] = False
            result["errors"].append("Filename is required")
            return

        ext = Path(filename).suffix.lower()

        if not ext:
            result["warnings"].append("File has no extension")
        elif ext not in self.allowed_extensions:
            result["valid"] = False
            result["errors"].append(f"File extension '{ext}' is not allowed")

        result["metadata"]["extension"] = ext
        result["metadata"]["filename"] = filename

    async def _validate_mime_type(
        self, content: bytes, filename: str, result: Dict[str, Any]
    ):
        """Validate MIME type using file content"""
        try:
            # Use python-magic to detect MIME type from content
            detected_mime = magic.from_buffer(content, mime=True)

            # Also get MIME type from filename
            guessed_mime, _ = mimetypes.guess_type(filename)

            result["metadata"]["detected_mime_type"] = detected_mime
            result["metadata"]["guessed_mime_type"] = guessed_mime

            # Check if detected MIME type is allowed
            if self.allowed_mime_types and detected_mime not in self.allowed_mime_types:
                result["valid"] = False
                result["errors"].append(f"MIME type '{detected_mime}' is not allowed")

            # Warn if detected and guessed MIME types don't match
            if guessed_mime and detected_mime != guessed_mime:
                result["warnings"].append(
                    f"Detected MIME type ({detected_mime}) differs from expected ({guessed_mime})"
                )

        except Exception as e:
            result["warnings"].append(f"Could not detect MIME type: {str(e)}")

    async def _validate_content(
        self, content: bytes, filename: str, result: Dict[str, Any]
    ):
        """Additional content validation (override in subclasses)"""
        pass


class ImageValidator(FileValidator):
    """Validator specifically for image files"""

    def __init__(
        self,
        max_file_size: int = 5 * 1024 * 1024,  # 5MB for images
        max_width: int = 4096,
        max_height: int = 4096,
        min_width: int = 1,
        min_height: int = 1,
        **kwargs,
    ):
        super().__init__(
            max_file_size=max_file_size,
            allowed_extensions={".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"},
            allowed_mime_types={
                "image/jpeg",
                "image/png",
                "image/gif",
                "image/bmp",
                "image/webp",
            },
            **kwargs,
        )
        self.max_width = max_width
        self.max_height = max_height
        self.min_width = min_width
        self.min_height = min_height

    async def _validate_content(
        self, content: bytes, filename: str, result: Dict[str, Any]
    ):
        """Validate image content"""
        try:
            # Open image with PIL
            from io import BytesIO

            image = Image.open(BytesIO(content))

            width, height = image.size

            result["metadata"]["width"] = width
            result["metadata"]["height"] = height
            result["metadata"]["format"] = image.format
            result["metadata"]["mode"] = image.mode

            # Validate dimensions
            if width > self.max_width or height > self.max_height:
                result["valid"] = False
                result["errors"].append(
                    f"Image dimensions ({width}x{height}) exceed maximum allowed ({self.max_width}x{self.max_height})"
                )

            if width < self.min_width or height < self.min_height:
                result["valid"] = False
                result["errors"].append(
                    f"Image dimensions ({width}x{height}) below minimum required ({self.min_width}x{self.min_height})"
                )

            # Check for potential issues
            if image.mode not in ["RGB", "RGBA", "L"]:
                result["warnings"].append(f"Unusual image mode: {image.mode}")

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Invalid image file: {str(e)}")


class DocumentValidator(FileValidator):
    """Validator specifically for document files"""

    def __init__(
        self, max_file_size: int = 20 * 1024 * 1024, **kwargs  # 20MB for documents
    ):
        super().__init__(
            max_file_size=max_file_size,
            allowed_extensions={".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"},
            allowed_mime_types={
                "application/pdf",
                "application/msword",
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "text/plain",
                "text/rtf",
                "application/vnd.oasis.opendocument.text",
            },
            **kwargs,
        )

    async def _validate_content(
        self, content: bytes, filename: str, result: Dict[str, Any]
    ):
        """Validate document content"""
        ext = Path(filename).suffix.lower()

        try:
            if ext == ".pdf":
                await self._validate_pdf(content, result)
            elif ext in [".txt", ".rtf"]:
                await self._validate_text(content, result)
            # Add more document type validations as needed

        except Exception as e:
            result["warnings"].append(f"Could not validate document content: {str(e)}")

    async def _validate_pdf(self, content: bytes, result: Dict[str, Any]):
        """Validate PDF content"""
        try:
            from io import BytesIO

            pdf_reader = pypdf.PdfReader(BytesIO(content))

            num_pages = len(pdf_reader.pages)
            result["metadata"]["num_pages"] = num_pages

            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                result["warnings"].append("PDF is encrypted")

            # Extract basic metadata
            if pdf_reader.metadata:
                result["metadata"]["pdf_title"] = pdf_reader.metadata.get("/Title", "")
                result["metadata"]["pdf_author"] = pdf_reader.metadata.get(
                    "/Author", ""
                )
                result["metadata"]["pdf_creator"] = pdf_reader.metadata.get(
                    "/Creator", ""
                )

        except Exception as e:
            result["valid"] = False
            result["errors"].append(f"Invalid PDF file: {str(e)}")

    async def _validate_text(self, content: bytes, result: Dict[str, Any]):
        """Validate text content"""
        try:
            # Try to decode as UTF-8
            text = content.decode("utf-8")

            result["metadata"]["character_count"] = len(text)
            result["metadata"]["line_count"] = text.count("\n") + 1
            result["metadata"]["encoding"] = "utf-8"

        except UnicodeDecodeError:
            try:
                # Try other common encodings
                for encoding in ["latin-1", "cp1252", "iso-8859-1"]:
                    text = content.decode(encoding)
                    result["metadata"]["encoding"] = encoding
                    result["warnings"].append(
                        f"Text file uses {encoding} encoding instead of UTF-8"
                    )
                    break
            except UnicodeDecodeError:
                result["valid"] = False
                result["errors"].append("Could not decode text file")


class VideoValidator(FileValidator):
    """Validator specifically for video files"""

    def __init__(
        self,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB for videos
        max_duration: int = 3600,  # 1 hour
        **kwargs,
    ):
        super().__init__(
            max_file_size=max_file_size,
            allowed_extensions={".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"},
            allowed_mime_types={
                "video/mp4",
                "video/avi",
                "video/quicktime",
                "video/x-ms-wmv",
                "video/x-flv",
                "video/webm",
            },
            **kwargs,
        )
        self.max_duration = max_duration

    async def _validate_content(
        self, content: bytes, filename: str, result: Dict[str, Any]
    ):
        """Validate video content"""
        try:
            # This would require ffmpeg-python or similar
            # For now, just basic validation
            result["warnings"].append("Video content validation not fully implemented")

        except Exception as e:
            result["warnings"].append(f"Could not validate video content: {str(e)}")


class AudioValidator(FileValidator):
    """Validator specifically for audio files"""

    def __init__(
        self,
        max_file_size: int = 50 * 1024 * 1024,  # 50MB for audio
        max_duration: int = 3600,  # 1 hour
        **kwargs,
    ):
        super().__init__(
            max_file_size=max_file_size,
            allowed_extensions={".mp3", ".wav", ".flac", ".aac", ".ogg"},
            allowed_mime_types={
                "audio/mpeg",
                "audio/wav",
                "audio/flac",
                "audio/aac",
                "audio/ogg",
            },
            **kwargs,
        )
        self.max_duration = max_duration

    async def _validate_content(
        self, content: bytes, filename: str, result: Dict[str, Any]
    ):
        """Validate audio content"""
        try:
            # This would require mutagen or similar for audio metadata
            # For now, just basic validation
            result["warnings"].append("Audio content validation not fully implemented")

        except Exception as e:
            result["warnings"].append(f"Could not validate audio content: {str(e)}")


def get_validator_for_file(filename: str, **kwargs) -> FileValidator:
    """Get appropriate validator based on file type"""

    ext = Path(filename).suffix.lower()

    # Image files
    if ext in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}:
        return ImageValidator(**kwargs)

    # Document files
    elif ext in {".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt"}:
        return DocumentValidator(**kwargs)

    # Video files
    elif ext in {".mp4", ".avi", ".mov", ".wmv", ".flv", ".webm"}:
        return VideoValidator(**kwargs)

    # Audio files
    elif ext in {".mp3", ".wav", ".flac", ".aac", ".ogg"}:
        return AudioValidator(**kwargs)

    # Default validator
    else:
        return FileValidator(**kwargs)
