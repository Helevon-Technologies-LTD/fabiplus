"""
Custom Authentication Methods and Middleware
Provides additional authentication options beyond the default OAuth2
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import get_current_active_user
from .models import User
from .registry import ModelRegistry

logger = logging.getLogger(__name__)

# Custom security schemes
bearer_scheme = HTTPBearer(auto_error=False)


class APIKeyAuth:
    """API Key Authentication"""

    def __init__(self, header_name: str = "X-API-Key"):
        self.header_name = header_name

    async def __call__(self, request: Request) -> Optional[User]:
        api_key = request.headers.get(self.header_name)
        if not api_key:
            return None

        # Validate API key against database
        session = ModelRegistry.get_session()
        try:
            # You would store API keys in a separate table
            # For now, we'll use a simple hash check
            user = (
                session.query(User)
                .filter(User.api_key == api_key, User.is_active.is_(True))
                .first()
            )
            return user
        finally:
            session.close()


class SessionAuth:
    """Session-based Authentication"""

    def __init__(self, session_key: str = "session_id"):
        self.session_key = session_key

    async def __call__(self, request: Request) -> Optional[User]:
        session_id = request.cookies.get(self.session_key)
        if not session_id:
            return None

        # Validate session against database/cache
        session = ModelRegistry.get_session()
        try:
            # You would store sessions in a separate table or Redis
            # For now, we'll decode the session
            user_id = self._decode_session(session_id)
            if user_id:
                user = session.get(User, user_id)
                if user and user.is_active:
                    return user
        finally:
            session.close()

        return None

    def _decode_session(self, session_id: str) -> Optional[str]:
        """Decode session ID to get user ID"""
        try:
            # Simple base64 decode - in production use proper session management
            import base64

            decoded = base64.b64decode(session_id).decode()
            return decoded.split(":")[0] if ":" in decoded else None
        except (ValueError, TypeError):
            return None


class CustomAuthMiddleware:
    """Custom Authentication Middleware"""

    def __init__(
        self,
        api_key_auth: bool = True,
        session_auth: bool = True,
        rate_limiting: bool = True,
    ):
        self.api_key_auth = APIKeyAuth() if api_key_auth else None
        self.session_auth = SessionAuth() if session_auth else None
        self.rate_limiting = rate_limiting
        self.rate_limit_store = {}  # In production, use Redis

    async def __call__(self, request: Request, call_next):
        # Rate limiting
        if self.rate_limiting:
            client_ip = request.client.host
            if self._is_rate_limited(client_ip):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded",
                )

        # Try different authentication methods
        user = None

        # Try API key authentication
        if self.api_key_auth:
            user = await self.api_key_auth(request)

        # Try session authentication if API key failed
        if not user and self.session_auth:
            user = await self.session_auth(request)

        # Add user to request state
        request.state.custom_user = user

        response = await call_next(request)
        return response

    def _is_rate_limited(self, client_ip: str) -> bool:
        """Simple rate limiting - 100 requests per minute"""
        now = datetime.now(timezone.utc)
        minute_ago = now - timedelta(minutes=1)

        if client_ip not in self.rate_limit_store:
            self.rate_limit_store[client_ip] = []

        # Clean old requests
        self.rate_limit_store[client_ip] = [
            req_time
            for req_time in self.rate_limit_store[client_ip]
            if req_time > minute_ago
        ]

        # Check limit
        if len(self.rate_limit_store[client_ip]) >= 100:
            return True

        # Add current request
        self.rate_limit_store[client_ip].append(now)
        return False


# Custom dependency functions
async def get_current_user_custom(request: Request) -> Optional[User]:
    """Get current user from custom authentication"""
    return getattr(request.state, "custom_user", None)


async def require_custom_auth(request: Request) -> User:
    """Require custom authentication"""
    user = await get_current_user_custom(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required"
        )
    return user


async def require_staff_custom(request: Request) -> User:
    """Require staff access with custom authentication"""
    user = await require_custom_auth(request)
    if not user.is_staff:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Staff access required"
        )
    return user


async def require_superuser_custom(request: Request) -> User:
    """Require superuser access with custom authentication"""
    user = await require_custom_auth(request)
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Superuser access required"
        )
    return user


# Multi-auth dependency (tries multiple auth methods)
class MultiAuth:
    """Multiple authentication methods dependency"""

    def __init__(self, oauth2: bool = True, api_key: bool = True, session: bool = True):
        self.oauth2 = oauth2
        self.api_key = APIKeyAuth() if api_key else None
        self.session = SessionAuth() if session else None

    async def __call__(self, request: Request) -> Optional[User]:
        user = None

        # Try OAuth2 first
        if self.oauth2:
            try:
                user = await get_current_active_user()
            except Exception:
                pass

        # Try custom auth methods
        if not user:
            user = await get_current_user_custom(request)

        return user


# Decorators for custom authentication
def custom_auth_required(func: Callable) -> Callable:
    """Decorator to require custom authentication"""

    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        if not request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request object not found",
            )

        user = await require_custom_auth(request)
        kwargs["current_user"] = user
        return await func(*args, **kwargs)

    return wrapper


def staff_required(func: Callable) -> Callable:
    """Decorator to require staff access"""

    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        if not request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request object not found",
            )

        user = await require_staff_custom(request)
        kwargs["current_user"] = user
        return await func(*args, **kwargs)

    return wrapper


def superuser_required(func: Callable) -> Callable:
    """Decorator to require superuser access"""

    async def wrapper(*args, **kwargs):
        request = kwargs.get("request")
        if not request:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Request object not found",
            )

        user = await require_superuser_custom(request)
        kwargs["current_user"] = user
        return await func(*args, **kwargs)

    return wrapper


# Utility functions
def generate_api_key() -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)


def hash_api_key(api_key: str) -> str:
    """Hash API key for storage"""
    return hashlib.sha256(api_key.encode()).hexdigest()


def create_session_token(user_id: str) -> str:
    """Create a session token"""
    import base64

    session_data = f"{user_id}:{datetime.now(timezone.utc).isoformat()}"
    return base64.b64encode(session_data.encode()).decode()


# Custom authentication backends
class CustomAuthBackend:
    """Custom authentication backend interface"""

    async def authenticate(self, request: Request) -> Optional[User]:
        """Authenticate user from request"""
        raise NotImplementedError

    async def get_user(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        session = ModelRegistry.get_session()
        try:
            return session.get(User, user_id)
        finally:
            session.close()


class DatabaseAuthBackend(CustomAuthBackend):
    """Database-based authentication backend"""

    async def authenticate(self, request: Request) -> Optional[User]:
        """Authenticate using database credentials"""
        # Implementation for database authentication
        pass


class LDAPAuthBackend(CustomAuthBackend):
    """LDAP authentication backend"""

    async def authenticate(self, request: Request) -> Optional[User]:
        """Authenticate using LDAP"""
        # Implementation for LDAP authentication
        pass
