"""
API routes for media management in FABI+ framework
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlmodel import Session, select

from fabiplus.core.auth import User, get_current_user
from fabiplus.core.database import get_session

from .handlers import FileDownloadHandler, FileUploadHandler
from .models import MediaFile, MediaFolder, MediaUploadSession
from .processors import DocumentProcessor, FileProcessor, ImageProcessor
from .storage import LocalFileStorage, StorageConfig
from .validators import get_validator_for_file


# Pydantic models for API
class MediaFileResponse(BaseModel):
    """Response model for media files"""

    id: UUID
    filename: str
    original_filename: str
    title: str
    description: str
    size: int
    content_type: str
    storage_url: str
    is_public: bool
    created_at: str
    thumbnails: Dict[str, str]
    width: Optional[int] = None
    height: Optional[int] = None


class MediaFolderResponse(BaseModel):
    """Response model for media folders"""

    id: UUID
    name: str
    slug: str
    description: str
    is_public: bool
    created_at: str
    file_count: int


class UploadResponse(BaseModel):
    """Response model for file uploads"""

    success: bool
    files: List[MediaFileResponse]
    errors: List[Dict[str, str]] = []


class ChunkedUploadResponse(BaseModel):
    """Response model for chunked uploads"""

    session_id: str
    status: str
    progress: float
    uploaded_chunks: int
    total_chunks: int
    file: Optional[MediaFileResponse] = None


# Create router
router = APIRouter(prefix="/media", tags=["Media"])

# Initialize storage and handlers
storage_config = StorageConfig()
storage = LocalFileStorage(storage_config)
processor = FileProcessor()
upload_handler = FileUploadHandler(
    storage, None, processor
)  # Validator will be set per request
download_handler = FileDownloadHandler(storage)


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: List[UploadFile] = File(...),
    folder_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    alt_text: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload one or more files"""

    uploaded_files = []
    errors = []

    # Parse tags
    tag_list = [tag.strip() for tag in tags.split(",")] if tags else []

    for file in files:
        try:
            # Get appropriate validator for file type
            validator = get_validator_for_file(file.filename)
            upload_handler.validator = validator

            # Upload file
            media_file = await upload_handler.upload_single_file(
                file=file,
                folder_id=folder_id,
                title=title,
                description=description,
                alt_text=alt_text,
                tags=tag_list,
                user_id=str(current_user.id),
                session=session,
            )

            uploaded_files.append(
                MediaFileResponse(
                    id=media_file.id,
                    filename=media_file.filename,
                    original_filename=media_file.original_filename,
                    title=media_file.title,
                    description=media_file.description,
                    size=media_file.size,
                    content_type=media_file.content_type,
                    storage_url=media_file.storage_url,
                    is_public=media_file.is_public,
                    created_at=media_file.created_at.isoformat(),
                    thumbnails=media_file.thumbnails,
                    width=media_file.width,
                    height=media_file.height,
                )
            )

        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})

    return UploadResponse(
        success=len(uploaded_files) > 0, files=uploaded_files, errors=errors
    )


@router.post("/upload/chunked/start", response_model=ChunkedUploadResponse)
async def start_chunked_upload(
    filename: str = Form(...),
    total_size: int = Form(...),
    chunk_size: int = Form(...),
    folder_id: Optional[str] = Form(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Start a chunked upload session"""

    upload_session = await upload_handler.start_chunked_upload(
        filename=filename,
        total_size=total_size,
        chunk_size=chunk_size,
        folder_id=folder_id,
        user_id=str(current_user.id),
        session=session,
    )

    return ChunkedUploadResponse(
        session_id=upload_session.session_id,
        status="started",
        progress=0.0,
        uploaded_chunks=0,
        total_chunks=upload_session.total_chunks,
    )


@router.post(
    "/upload/chunked/{session_id}/chunk/{chunk_number}",
    response_model=ChunkedUploadResponse,
)
async def upload_chunk(
    session_id: str,
    chunk_number: int,
    chunk: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Upload a file chunk"""

    chunk_data = await chunk.read()

    result = await upload_handler.upload_chunk(
        session_id=session_id,
        chunk_number=chunk_number,
        chunk_data=chunk_data,
        session=session,
    )

    file_response = None
    if result.get("file"):
        media_file = result["file"]
        file_response = MediaFileResponse(
            id=media_file.id,
            filename=media_file.filename,
            original_filename=media_file.original_filename,
            title=media_file.title,
            description=media_file.description,
            size=media_file.size,
            content_type=media_file.content_type,
            storage_url=media_file.storage_url,
            is_public=media_file.is_public,
            created_at=media_file.created_at.isoformat(),
            thumbnails=media_file.thumbnails,
            width=media_file.width,
            height=media_file.height,
        )

    return ChunkedUploadResponse(
        session_id=session_id,
        status=result["status"],
        progress=result["progress"],
        uploaded_chunks=result.get("uploaded_chunks", 0),
        total_chunks=result.get("total_chunks", 0),
        file=file_response,
    )


@router.get("/files", response_model=List[MediaFileResponse])
async def list_files(
    folder_id: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    content_type: Optional[str] = Query(None),
    limit: int = Query(50, le=100),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List media files with filtering and pagination"""

    query = select(MediaFile)

    # Apply filters
    if folder_id:
        query = query.where(MediaFile.folder_id == folder_id)

    if search:
        query = query.where(
            MediaFile.title.contains(search)
            | MediaFile.original_filename.contains(search)
            | MediaFile.description.contains(search)
        )

    if content_type:
        query = query.where(MediaFile.content_type.startswith(content_type))

    # Apply pagination
    query = query.offset(offset).limit(limit)

    files = session.exec(query).all()

    return [
        MediaFileResponse(
            id=file.id,
            filename=file.filename,
            original_filename=file.original_filename,
            title=file.title,
            description=file.description,
            size=file.size,
            content_type=file.content_type,
            storage_url=file.storage_url,
            is_public=file.is_public,
            created_at=file.created_at.isoformat(),
            thumbnails=file.thumbnails,
            width=file.width,
            height=file.height,
        )
        for file in files
    ]


@router.get("/files/{file_id}", response_model=MediaFileResponse)
async def get_file(
    file_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Get media file details"""

    media_file = session.get(MediaFile, file_id)
    if not media_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    return MediaFileResponse(
        id=media_file.id,
        filename=media_file.filename,
        original_filename=media_file.original_filename,
        title=media_file.title,
        description=media_file.description,
        size=media_file.size,
        content_type=media_file.content_type,
        storage_url=media_file.storage_url,
        is_public=media_file.is_public,
        created_at=media_file.created_at.isoformat(),
        thumbnails=media_file.thumbnails,
        width=media_file.width,
        height=media_file.height,
    )


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    as_attachment: bool = Query(False),
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(get_current_user),
):
    """Download a media file"""

    from fastapi import Request

    # Create a mock request for the download handler
    # In a real implementation, you'd pass the actual request
    class MockRequest:
        def __init__(self):
            self.headers = {}

    mock_request = MockRequest()

    return await download_handler.download_file(
        file_id=str(file_id),
        request=mock_request,
        session=session,
        user_id=str(current_user.id) if current_user else None,
        as_attachment=as_attachment,
    )


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Delete a media file"""

    media_file = session.get(MediaFile, file_id)
    if not media_file:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )

    # Check permissions
    if str(media_file.uploaded_by) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied"
        )

    # Delete from storage
    await storage.delete(media_file.storage_path)

    # Delete from database
    session.delete(media_file)
    session.commit()

    return {"message": "File deleted successfully"}


@router.get("/folders", response_model=List[MediaFolderResponse])
async def list_folders(
    parent_id: Optional[str] = Query(None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """List media folders"""

    query = select(MediaFolder)

    if parent_id:
        query = query.where(MediaFolder.parent_id == parent_id)
    else:
        query = query.where(MediaFolder.parent_id.is_(None))

    folders = session.exec(query).all()

    return [
        MediaFolderResponse(
            id=folder.id,
            name=folder.name,
            slug=folder.slug,
            description=folder.description,
            is_public=folder.is_public,
            created_at=folder.created_at.isoformat(),
            file_count=len(folder.files),
        )
        for folder in folders
    ]


@router.post("/folders", response_model=MediaFolderResponse)
async def create_folder(
    name: str = Form(...),
    description: str = Form(""),
    parent_id: Optional[str] = Form(None),
    is_public: bool = Form(True),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Create a new media folder"""

    folder = MediaFolder(
        name=name,
        description=description,
        parent_id=parent_id,
        is_public=is_public,
        created_by=current_user.id,
    )

    session.add(folder)
    session.commit()
    session.refresh(folder)

    return MediaFolderResponse(
        id=folder.id,
        name=folder.name,
        slug=folder.slug,
        description=folder.description,
        is_public=folder.is_public,
        created_at=folder.created_at.isoformat(),
        file_count=0,
    )
