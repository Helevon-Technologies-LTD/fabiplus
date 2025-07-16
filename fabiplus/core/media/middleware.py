"""
Middleware for media handling in FABI+ framework
"""

import os
from pathlib import Path
from typing import Callable, Optional

from fastapi import HTTPException, Request, Response, status
from fastapi.responses import FileResponse, StreamingResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .storage import LocalFileStorage, StorageConfig


class MediaMiddleware(BaseHTTPMiddleware):
    """Middleware to serve media files"""

    def __init__(
        self,
        app: ASGIApp,
        media_url_prefix: str = "/media",
        media_root: str = "media",
        max_age: int = 3600,
        enable_range_requests: bool = True,
    ):
        super().__init__(app)
        self.media_url_prefix = media_url_prefix.rstrip("/")
        self.media_root = Path(media_root)
        self.max_age = max_age
        self.enable_range_requests = enable_range_requests

        # Ensure media directory exists
        self.media_root.mkdir(parents=True, exist_ok=True)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Handle media file requests"""

        # Check if this is a media request
        if not request.url.path.startswith(self.media_url_prefix):
            return await call_next(request)

        # Extract file path
        file_path = request.url.path[len(self.media_url_prefix) :].lstrip("/")

        if not file_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Security check - prevent directory traversal
        try:
            full_path = (self.media_root / file_path).resolve()
            if not str(full_path).startswith(str(self.media_root.resolve())):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
                )
        except (OSError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file path"
            )

        # Check if file exists
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
            )

        # Handle range requests for video/audio streaming
        if self.enable_range_requests and request.headers.get("range"):
            return await self._handle_range_request(request, full_path)

        # Regular file response
        return await self._create_file_response(request, full_path)

    async def _handle_range_request(
        self, request: Request, file_path: Path
    ) -> StreamingResponse:
        """Handle HTTP range requests for streaming"""

        range_header = request.headers.get("range")
        if not range_header:
            return await self._create_file_response(request, file_path)

        # Parse range header
        try:
            range_match = range_header.replace("bytes=", "").split("-")
            start = int(range_match[0]) if range_match[0] else 0

            file_size = file_path.stat().st_size
            end = int(range_match[1]) if range_match[1] else file_size - 1

            # Validate range
            if start >= file_size or end >= file_size or start > end:
                raise HTTPException(
                    status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                    detail="Invalid range",
                )

            content_length = end - start + 1

            # Create streaming response
            def file_generator():
                with open(file_path, "rb") as f:
                    f.seek(start)
                    remaining = content_length

                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk

            # Determine content type
            import mimetypes

            content_type, _ = mimetypes.guess_type(str(file_path))
            content_type = content_type or "application/octet-stream"

            return StreamingResponse(
                file_generator(),
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                media_type=content_type,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{file_size}",
                    "Content-Length": str(content_length),
                    "Accept-Ranges": "bytes",
                    "Cache-Control": f"public, max-age={self.max_age}",
                },
            )

        except (ValueError, IndexError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid range header"
            )

    async def _create_file_response(
        self, request: Request, file_path: Path
    ) -> FileResponse:
        """Create regular file response"""

        # Determine content type
        import mimetypes

        content_type, _ = mimetypes.guess_type(str(file_path))
        content_type = content_type or "application/octet-stream"

        # Check if client supports compression
        accept_encoding = request.headers.get("accept-encoding", "")

        # Create response headers
        headers = {
            "Cache-Control": f"public, max-age={self.max_age}",
            "Accept-Ranges": "bytes" if self.enable_range_requests else "none",
        }

        # Add ETag for caching
        stat = file_path.stat()
        etag = f'"{stat.st_mtime}-{stat.st_size}"'
        headers["ETag"] = etag

        # Check if client has cached version
        if_none_match = request.headers.get("if-none-match")
        if if_none_match == etag:
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=headers)

        return FileResponse(
            path=str(file_path), media_type=content_type, headers=headers
        )


class MediaSecurityMiddleware(BaseHTTPMiddleware):
    """Security middleware for media files"""

    def __init__(
        self,
        app: ASGIApp,
        media_url_prefix: str = "/media",
        require_auth: bool = False,
        allowed_origins: Optional[list] = None,
        rate_limit: Optional[int] = None,
    ):
        super().__init__(app)
        self.media_url_prefix = media_url_prefix.rstrip("/")
        self.require_auth = require_auth
        self.allowed_origins = allowed_origins or []
        self.rate_limit = rate_limit
        self._request_counts = {}  # Simple in-memory rate limiting

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply security checks to media requests"""

        # Only apply to media requests
        if not request.url.path.startswith(self.media_url_prefix):
            return await call_next(request)

        # Check origin if specified
        if self.allowed_origins:
            origin = request.headers.get("origin")
            if origin and origin not in self.allowed_origins:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="Origin not allowed"
                )

        # Simple rate limiting
        if self.rate_limit:
            client_ip = request.client.host
            current_count = self._request_counts.get(client_ip, 0)

            if current_count >= self.rate_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                )

            self._request_counts[client_ip] = current_count + 1

        # Authentication check
        if self.require_auth:
            # Check for authentication token
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            # TODO: Validate token
            # For now, just check if token exists
            token = auth_header.split(" ")[1]
            if not token:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
                )

        response = await call_next(request)

        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"

        return response


class MediaCompressionMiddleware(BaseHTTPMiddleware):
    """Middleware for compressing media responses"""

    def __init__(
        self,
        app: ASGIApp,
        media_url_prefix: str = "/media",
        compress_types: Optional[list] = None,
        min_size: int = 1024,
    ):
        super().__init__(app)
        self.media_url_prefix = media_url_prefix.rstrip("/")
        self.compress_types = compress_types or [
            "text/plain",
            "text/css",
            "text/javascript",
            "application/javascript",
            "application/json",
            "application/xml",
            "text/xml",
        ]
        self.min_size = min_size

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Apply compression to eligible media responses"""

        # Only apply to media requests
        if not request.url.path.startswith(self.media_url_prefix):
            return await call_next(request)

        response = await call_next(request)

        # Check if compression is supported by client
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding:
            return response

        # Check if content type is compressible
        content_type = response.headers.get("content-type", "")
        if not any(ct in content_type for ct in self.compress_types):
            return response

        # Check content length
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) < self.min_size:
            return response

        # TODO: Implement actual compression
        # For now, just add the header to indicate compression support
        response.headers["Vary"] = "Accept-Encoding"

        return response
