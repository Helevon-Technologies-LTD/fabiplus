"""
FABI+ Framework Logging Middleware
Provides request/response logging and performance monitoring
"""

import json
import logging
import time
import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..conf.settings import settings

# Configure logger
logger = logging.getLogger("fabiplus.requests")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Logging middleware for FABI+ framework
    Logs all requests and responses with performance metrics
    """

    def __init__(self, app, log_requests: bool = True, log_responses: bool = True):
        super().__init__(app)
        self.log_requests = log_requests
        self.log_responses = log_responses

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request through logging middleware"""

        # Generate request ID
        request_id = str(uuid.uuid4())

        # Start timing
        start_time = time.time()

        # Log request
        if self.log_requests:
            await self._log_request(request, request_id)

        # Process request
        try:
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Add request ID and timing to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = str(process_time)

            # Log response
            if self.log_responses:
                await self._log_response(request, response, request_id, process_time)

            return response

        except Exception as e:
            # Log error
            process_time = time.time() - start_time
            await self._log_error(request, e, request_id, process_time)
            raise

    async def _log_request(self, request: Request, request_id: str):
        """Log incoming request"""

        # Get client info
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")

        # Skip body logging for form data to avoid consuming the request body
        # This prevents issues with login forms and other form submissions
        body_data = None
        content_type = request.headers.get("content-type", "")
        if request.method in ["POST", "PUT", "PATCH"] and content_type.startswith(
            "application/json"
        ):
            try:
                # Only read body for JSON requests, not form data
                body = await request.body()
                if body:
                    body_data = json.loads(body.decode())
                    # Mask sensitive fields
                    body_data = self._mask_sensitive_data(body_data)
            except Exception:
                body_data = "<unable to parse>"
        elif request.method in ["POST", "PUT", "PATCH"]:
            # For form data, just log that it's present without consuming it
            content_length = request.headers.get("content-length", "0")
            body_data = f"<form-data: {content_length} bytes>"

        log_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "headers": dict(request.headers),
            "client_ip": client_ip,
            "user_agent": user_agent,
            "body": body_data,
        }

        logger.info(
            f"Request {request_id}: {request.method} {request.url.path}", extra=log_data
        )

    async def _log_response(
        self, request: Request, response: Response, request_id: str, process_time: float
    ):
        """Log outgoing response"""

        # Don't try to read response body to avoid content-length issues
        response_data = None

        log_data = {
            "request_id": request_id,
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "process_time": process_time,
            "response_size": response.headers.get("content-length", "unknown"),
            "response_data": response_data,
        }

        # Log level based on status code
        if response.status_code >= 500:
            log_level = logging.ERROR
        elif response.status_code >= 400:
            log_level = logging.WARNING
        else:
            log_level = logging.INFO

        logger.log(
            log_level,
            f"Response {request_id}: {response.status_code} ({process_time:.3f}s)",
            extra=log_data,
        )

    async def _log_error(
        self, request: Request, error: Exception, request_id: str, process_time: float
    ):
        """Log request error"""

        log_data = {
            "request_id": request_id,
            "method": request.method,
            "url": str(request.url),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "process_time": process_time,
        }

        logger.error(
            f"Error {request_id}: {type(error).__name__} - {str(error)}",
            extra=log_data,
            exc_info=True,
        )

    def _get_client_ip(self, request: Request) -> str:
        """Get client IP address"""
        # Check for forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        return request.client.host if request.client else "unknown"

    def _mask_sensitive_data(self, data):
        """Mask sensitive data in logs"""
        if not isinstance(data, dict):
            return data

        sensitive_fields = [
            "password",
            "token",
            "secret",
            "key",
            "authorization",
            "credit_card",
            "ssn",
            "social_security",
            "api_key",
        ]

        masked_data = {}
        for key, value in data.items():
            if any(
                sensitive_field in key.lower() for sensitive_field in sensitive_fields
            ):
                masked_data[key] = "***MASKED***"
            elif isinstance(value, dict):
                masked_data[key] = self._mask_sensitive_data(value)
            elif isinstance(value, list):
                masked_data[key] = [
                    self._mask_sensitive_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                masked_data[key] = value

        return masked_data


class PerformanceMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Performance monitoring middleware
    Tracks response times and identifies slow endpoints
    """

    def __init__(self, app, slow_request_threshold: float = 1.0):
        super().__init__(app)
        self.slow_request_threshold = slow_request_threshold
        self.performance_logger = logging.getLogger("fabiplus.performance")

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Monitor request performance"""

        start_time = time.time()

        response = await call_next(request)

        process_time = time.time() - start_time

        # Log slow requests
        if process_time > self.slow_request_threshold:
            self.performance_logger.warning(
                f"Slow request: {request.method} {request.url.path} took {process_time:.3f}s",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "process_time": process_time,
                    "status_code": response.status_code,
                },
            )

        # Add performance metrics to response headers
        response.headers["X-Response-Time"] = f"{process_time:.3f}"

        return response
