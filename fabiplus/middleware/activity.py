"""
FABI+ Framework Activity Logging Middleware
Automatically logs user activities and API requests
"""

import time
import uuid
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.activity import ActivityLevel, ActivityLogger, ActivityType
from ..core.models import ModelRegistry


class ActivityLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log user activities and API requests"""

    def __init__(
        self, app, log_all_requests: bool = False, exclude_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.log_all_requests = log_all_requests
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
            "/static/",
            "/admin/static/",
            "/health",
            "/metrics",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and log activity"""
        start_time = time.time()

        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)

        # Get user context
        user = None
        try:
            # Try to get user from admin session cookie
            token = request.cookies.get("admin_token")
            if token:
                from jose import jwt

                from ..conf.settings import settings
                from ..core.models import User

                payload = jwt.decode(
                    token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
                )
                user_id = payload.get("sub")
                if user_id:
                    with ModelRegistry.get_session() as session:
                        user = session.get(User, user_id)
        except Exception:
            # If we can't get user, continue without it
            pass

        # Get request context
        user_ip = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")

        # Process request
        response = await call_next(request)

        # Calculate response time
        response_time = time.time() - start_time

        # Determine if we should log this request
        should_log = self._should_log_request(request, response, user)

        if should_log:
            # Log the activity asynchronously (don't block response)
            try:
                await self._log_request_activity(
                    request=request,
                    response=response,
                    user=user,
                    user_ip=user_ip,
                    user_agent=user_agent,
                    response_time=response_time,
                )
            except Exception as e:
                # Don't let logging errors affect the response
                print(f"Activity logging error: {e}")

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers first (for reverse proxies)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip

        # Fallback to direct client IP
        if hasattr(request, "client") and request.client:
            return request.client.host

        return "unknown"

    def _should_log_request(self, request: Request, response: Response, user) -> bool:
        """Determine if this request should be logged"""
        path = request.url.path
        method = request.method
        status_code = response.status_code

        # Always log authentication activities
        if "/login" in path or "/logout" in path:
            return True

        # Always log admin activities for authenticated users
        if "/admin/" in path and user:
            return True

        # Log API activities for authenticated users
        if "/api/" in path and user:
            return True

        # Log errors for all users
        if status_code >= 400:
            return True

        # Log all requests if configured
        if self.log_all_requests:
            return True

        return False

    async def _log_request_activity(
        self,
        request: Request,
        response: Response,
        user,
        user_ip: str,
        user_agent: str,
        response_time: float,
    ):
        """Log the request activity"""
        path = request.url.path
        method = request.method
        status_code = response.status_code

        # Determine activity type and details
        activity_type, action, description, level = self._analyze_request(
            request, response, user
        )

        # Prepare request context
        request_context = {
            "user_ip": user_ip,
            "user_agent": user_agent,
            "method": method,
            "path": path,
            "status_code": status_code,
            "response_time": response_time,
        }

        # Additional metadata
        metadata = {
            "query_params": dict(request.query_params),
            "path_params": getattr(request, "path_params", {}),
            "response_time_ms": round(response_time * 1000, 2),
        }

        # Log the activity
        ActivityLogger.log_activity(
            activity_type=activity_type,
            action=action,
            description=description,
            user=user,
            user_ip=user_ip,
            user_agent=user_agent,
            method=method,
            path=path,
            status_code=status_code,
            response_time=response_time,
            level=level,
            metadata=metadata,
        )

    def _analyze_request(self, request: Request, response: Response, user) -> tuple:
        """Analyze request to determine activity type and details"""
        path = request.url.path
        method = request.method
        status_code = response.status_code

        # Authentication activities
        if "/login" in path:
            if status_code < 400:
                return (
                    ActivityType.LOGIN,
                    f"login_{user.username if user else 'unknown'}",
                    f"User login: {user.email if user else 'unknown'}",
                    ActivityLevel.NORMAL,
                )
            else:
                return (
                    ActivityType.LOGIN,
                    "login_failed",
                    "Failed login attempt",
                    ActivityLevel.HIGH,
                )

        if "/logout" in path:
            return (
                ActivityType.LOGOUT,
                f"logout_{user.username if user else 'unknown'}",
                f"User logout: {user.email if user else 'unknown'}",
                ActivityLevel.NORMAL,
            )

        # Admin activities
        if "/admin/" in path:
            if "add" in path and method == "POST":
                model_name = self._extract_model_from_path(path)
                return (
                    ActivityType.CREATE,
                    f"admin_create_{model_name}",
                    f"Created {model_name} via admin",
                    ActivityLevel.NORMAL,
                )
            elif method == "POST" and status_code < 400:
                model_name = self._extract_model_from_path(path)
                return (
                    ActivityType.UPDATE,
                    f"admin_update_{model_name}",
                    f"Updated {model_name} via admin",
                    ActivityLevel.NORMAL,
                )
            elif method == "DELETE":
                model_name = self._extract_model_from_path(path)
                return (
                    ActivityType.DELETE,
                    f"admin_delete_{model_name}",
                    f"Deleted {model_name} via admin",
                    ActivityLevel.HIGH,
                )
            else:
                return (
                    ActivityType.ADMIN_ACCESS,
                    "admin_access",
                    f"Admin access: {path}",
                    ActivityLevel.LOW,
                )

        # API activities
        if "/api/" in path:
            model_name = self._extract_model_from_path(path)

            if method == "POST":
                return (
                    ActivityType.CREATE,
                    f"api_create_{model_name}",
                    f"Created {model_name} via API",
                    ActivityLevel.NORMAL,
                )
            elif method in ["PUT", "PATCH"]:
                return (
                    ActivityType.UPDATE,
                    f"api_update_{model_name}",
                    f"Updated {model_name} via API",
                    ActivityLevel.NORMAL,
                )
            elif method == "DELETE":
                return (
                    ActivityType.DELETE,
                    f"api_delete_{model_name}",
                    f"Deleted {model_name} via API",
                    ActivityLevel.HIGH,
                )
            else:
                return (
                    ActivityType.API_CALL,
                    f"api_call_{method.lower()}",
                    f"API call: {method} {path}",
                    ActivityLevel.LOW,
                )

        # Error activities
        if status_code >= 400:
            level = ActivityLevel.HIGH if status_code >= 500 else ActivityLevel.NORMAL
            return (
                ActivityType.ERROR,
                f"error_{status_code}",
                f"HTTP {status_code} error: {path}",
                level,
            )

        # Default system activity
        return (
            ActivityType.SYSTEM,
            "system_request",
            f"System request: {method} {path}",
            ActivityLevel.LOW,
        )

    def _extract_model_from_path(self, path: str) -> str:
        """Extract model name from URL path"""
        parts = path.strip("/").split("/")

        # For admin paths: /admin/model_name/...
        if "admin" in parts:
            admin_index = parts.index("admin")
            if len(parts) > admin_index + 1:
                return parts[admin_index + 1]

        # For API paths: /api/v1/model_name/...
        if "api" in parts:
            api_index = parts.index("api")
            # Skip version if present
            start_index = (
                api_index + 2
                if len(parts) > api_index + 1 and parts[api_index + 1].startswith("v")
                else api_index + 1
            )
            if len(parts) > start_index:
                return parts[start_index]

        return "unknown"
