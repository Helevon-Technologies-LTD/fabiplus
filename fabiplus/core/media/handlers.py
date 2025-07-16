"""
File upload and download handlers for FABI+ media system
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Optional

import aiofiles
from fastapi import HTTPException, Request, Response, UploadFile, status
from fastapi.responses import FileResponse, StreamingResponse
from sqlmodel import Session, select

from .models import MediaFile, MediaFolder, MediaUploadSession
from .processors import FileProcessor
from .storage import FileMetadata, FileStorage, StorageConfig
from .validators import FileValidator


class FileUploadHandler:
    """Handles file uploads with validation, processing, and storage"""

    def __init__(
        self, storage: FileStorage, validator: FileValidator, processor: FileProcessor
    ):
        self.storage = storage
        self.validator = validator
        self.processor = processor

    async def upload_single_file(
        self,
        file: UploadFile,
        folder_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        alt_text: Optional[str] = None,
        tags: Optional[List[str]] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> MediaFile:
        """Upload a single file"""

        # Validate file
        await self.validator.validate(file)

        # Determine folder
        folder = None
        if folder_id and session:
            folder = session.get(MediaFolder, folder_id)
            if not folder:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found"
                )

        # Save file to storage
        file_content = await file.read()
        await file.seek(0)

        storage_metadata = await self.storage.save(
            file.file, file.filename, folder=folder.slug if folder else ""
        )

        # Process file (generate thumbnails, etc.)
        processed_data = await self.processor.process(file_content, storage_metadata)

        # Create database record
        media_file = MediaFile(
            filename=storage_metadata.filename,
            original_filename=file.filename,
            title=title or file.filename,
            description=description or "",
            alt_text=alt_text or "",
            size=storage_metadata.size,
            content_type=storage_metadata.content_type,
            extension=storage_metadata.extension,
            storage_backend=self.storage.__class__.__name__.lower(),
            storage_path=storage_metadata.path,
            storage_url=storage_metadata.url,
            hash_md5=storage_metadata.hash_md5,
            hash_sha256=storage_metadata.hash_sha256,
            folder_id=folder.id if folder else None,
            tags=tags or [],
            uploaded_by=user_id,
            width=processed_data.get("width"),
            height=processed_data.get("height"),
            duration=processed_data.get("duration"),
            thumbnails=processed_data.get("thumbnails", {}),
            variants=processed_data.get("variants", {}),
        )

        if session:
            session.add(media_file)
            session.commit()
            session.refresh(media_file)

        return media_file

    async def upload_multiple_files(
        self,
        files: List[UploadFile],
        folder_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> List[MediaFile]:
        """Upload multiple files"""

        uploaded_files = []
        errors = []

        for file in files:
            try:
                media_file = await self.upload_single_file(
                    file=file, folder_id=folder_id, user_id=user_id, session=session
                )
                uploaded_files.append(media_file)
            except Exception as e:
                errors.append({"filename": file.filename, "error": str(e)})

        if errors and not uploaded_files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"message": "All uploads failed", "errors": errors},
            )

        return uploaded_files

    async def start_chunked_upload(
        self,
        filename: str,
        total_size: int,
        chunk_size: int,
        folder_id: Optional[str] = None,
        user_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> MediaUploadSession:
        """Start a chunked upload session"""

        import uuid

        session_id = str(uuid.uuid4())
        total_chunks = (total_size + chunk_size - 1) // chunk_size

        # Create temporary storage path
        temp_dir = Path(tempfile.gettempdir()) / "fabiplus_uploads"
        temp_dir.mkdir(exist_ok=True)
        temp_path = temp_dir / session_id

        upload_session = MediaUploadSession(
            session_id=session_id,
            filename=filename,
            total_size=total_size,
            chunk_size=chunk_size,
            total_chunks=total_chunks,
            expires_at=datetime.now() + timedelta(hours=24),
            uploaded_by=user_id,
            temp_storage_path=str(temp_path),
            target_folder_id=folder_id,
        )

        if session:
            session.add(upload_session)
            session.commit()
            session.refresh(upload_session)

        return upload_session

    async def upload_chunk(
        self,
        session_id: str,
        chunk_number: int,
        chunk_data: bytes,
        session: Optional[Session] = None,
    ) -> Dict[str, Any]:
        """Upload a file chunk"""

        if not session:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Database session required",
            )

        # Get upload session
        upload_session = session.exec(
            select(MediaUploadSession).where(
                MediaUploadSession.session_id == session_id
            )
        ).first()

        if not upload_session:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Upload session not found"
            )

        if upload_session.is_expired:
            raise HTTPException(
                status_code=status.HTTP_410_GONE, detail="Upload session expired"
            )

        # Save chunk to temporary file
        chunk_path = Path(upload_session.temp_storage_path + f".chunk_{chunk_number}")

        async with aiofiles.open(chunk_path, "wb") as f:
            await f.write(chunk_data)

        # Update session
        upload_session.add_chunk(chunk_number)
        session.commit()

        # If upload is complete, assemble file
        if upload_session.is_complete:
            final_file = await self._assemble_chunks(upload_session, session)
            return {"status": "complete", "file": final_file, "progress": 100.0}

        return {
            "status": "in_progress",
            "progress": upload_session.progress_percentage,
            "uploaded_chunks": len(upload_session.uploaded_chunks),
            "total_chunks": upload_session.total_chunks,
        }

    async def _assemble_chunks(
        self, upload_session: MediaUploadSession, session: Session
    ) -> MediaFile:
        """Assemble uploaded chunks into final file"""

        # Create final file path
        final_path = Path(upload_session.temp_storage_path + ".final")

        # Assemble chunks
        async with aiofiles.open(final_path, "wb") as final_file:
            for chunk_num in range(upload_session.total_chunks):
                chunk_path = Path(
                    upload_session.temp_storage_path + f".chunk_{chunk_num}"
                )
                if chunk_path.exists():
                    async with aiofiles.open(chunk_path, "rb") as chunk_file:
                        chunk_data = await chunk_file.read()
                        await final_file.write(chunk_data)

                    # Clean up chunk file
                    chunk_path.unlink()

        # Upload assembled file to storage
        with open(final_path, "rb") as f:
            storage_metadata = await self.storage.save(
                f, upload_session.filename, folder=""  # TODO: Use folder from session
            )

        # Process file
        with open(final_path, "rb") as f:
            file_content = f.read()

        processed_data = await self.processor.process(file_content, storage_metadata)

        # Create database record
        media_file = MediaFile(
            filename=storage_metadata.filename,
            original_filename=upload_session.filename,
            title=upload_session.filename,
            size=storage_metadata.size,
            content_type=storage_metadata.content_type,
            extension=storage_metadata.extension,
            storage_backend=self.storage.__class__.__name__.lower(),
            storage_path=storage_metadata.path,
            storage_url=storage_metadata.url,
            hash_md5=storage_metadata.hash_md5,
            hash_sha256=storage_metadata.hash_sha256,
            folder_id=upload_session.target_folder_id,
            uploaded_by=upload_session.uploaded_by,
            width=processed_data.get("width"),
            height=processed_data.get("height"),
            duration=processed_data.get("duration"),
            thumbnails=processed_data.get("thumbnails", {}),
            variants=processed_data.get("variants", {}),
        )

        session.add(media_file)
        session.commit()
        session.refresh(media_file)

        # Clean up temporary files
        final_path.unlink(missing_ok=True)

        return media_file


class FileDownloadHandler:
    """Handles file downloads with access control and streaming"""

    def __init__(self, storage: FileStorage):
        self.storage = storage

    async def download_file(
        self,
        file_id: str,
        request: Request,
        session: Session,
        user_id: Optional[str] = None,
        as_attachment: bool = False,
    ) -> Response:
        """Download a file with access control"""

        # Get file from database
        media_file = session.get(MediaFile, file_id)
        if not media_file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Check access permissions
        if not await self._check_access_permission(media_file, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Update access tracking
        media_file.increment_download_count()
        session.commit()

        # Get file from storage
        if not await self.storage.exists(media_file.storage_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found in storage",
            )

        # Determine response type
        if as_attachment:
            return await self._create_download_response(media_file)
        else:
            return await self._create_streaming_response(media_file, request)

    async def _check_access_permission(
        self, media_file: MediaFile, user_id: Optional[str]
    ) -> bool:
        """Check if user has permission to access file"""

        # Public files are accessible to everyone
        if media_file.is_public:
            return True

        # Private files require authentication
        if not user_id:
            return False

        # File owner can always access
        if str(media_file.uploaded_by) == user_id:
            return True

        # Check custom permissions
        permissions = media_file.access_permissions or {}
        allowed_users = permissions.get("allowed_users", [])

        return user_id in allowed_users

    async def _create_download_response(self, media_file: MediaFile) -> FileResponse:
        """Create file download response"""

        # For local storage, use FileResponse
        if media_file.storage_backend == "localfilestorage":
            file_path = Path(self.storage.base_path) / media_file.storage_path

            return FileResponse(
                path=str(file_path),
                filename=media_file.original_filename,
                media_type=media_file.content_type,
                headers={
                    "Content-Disposition": f"attachment; filename={media_file.original_filename}"
                },
            )

        # For cloud storage, redirect to signed URL
        else:
            signed_url = await self.storage.get_url(
                media_file.storage_path, expires_in=3600
            )
            return Response(
                status_code=status.HTTP_302_FOUND, headers={"Location": signed_url}
            )

    async def _create_streaming_response(
        self, media_file: MediaFile, request: Request
    ) -> StreamingResponse:
        """Create streaming response for file"""

        # Handle range requests for video/audio streaming
        range_header = request.headers.get("range")

        if range_header and media_file.is_video or media_file.is_audio:
            return await self._create_range_response(media_file, range_header)

        # Regular streaming response
        file_path = Path(self.storage.base_path) / media_file.storage_path

        async def file_generator():
            async with aiofiles.open(file_path, "rb") as f:
                while chunk := await f.read(8192):
                    yield chunk

        return StreamingResponse(
            file_generator(),
            media_type=media_file.content_type,
            headers={"Content-Length": str(media_file.size), "Accept-Ranges": "bytes"},
        )

    async def _create_range_response(
        self, media_file: MediaFile, range_header: str
    ) -> StreamingResponse:
        """Create partial content response for range requests"""

        # Parse range header
        range_match = range_header.replace("bytes=", "").split("-")
        start = int(range_match[0]) if range_match[0] else 0
        end = int(range_match[1]) if range_match[1] else media_file.size - 1

        content_length = end - start + 1

        file_path = Path(self.storage.base_path) / media_file.storage_path

        async def range_generator():
            async with aiofiles.open(file_path, "rb") as f:
                await f.seek(start)
                remaining = content_length

                while remaining > 0:
                    chunk_size = min(8192, remaining)
                    chunk = await f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(
            range_generator(),
            status_code=status.HTTP_206_PARTIAL_CONTENT,
            media_type=media_file.content_type,
            headers={
                "Content-Range": f"bytes {start}-{end}/{media_file.size}",
                "Content-Length": str(content_length),
                "Accept-Ranges": "bytes",
            },
        )
