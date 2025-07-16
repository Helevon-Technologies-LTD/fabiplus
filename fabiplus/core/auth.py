"""
FABI+ Framework Authentication System
OAuth2-based authentication with JWT tokens and custom backend support
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from sqlmodel import select

from ..conf.settings import settings
from .models import ModelRegistry, User

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme for documentation
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token", scheme_name="OAuth2PasswordBearer"
)


class AuthenticationError(HTTPException):
    """Custom authentication error"""

    def __init__(self, detail: str = "Authentication failed"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class PermissionError(HTTPException):
    """Custom permission error"""

    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
        )


class BaseAuthBackend:
    """
    Base authentication backend class
    Can be extended for custom authentication logic
    """

    def hash_password(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
        to_encode.update({"exp": expire})

        encoded_jwt = jwt.encode(
            to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
        )
        return encoded_jwt

    def decode_access_token(self, token: str) -> Dict[str, Any]:
        """Decode JWT access token"""
        try:
            payload = jwt.decode(
                token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
            )
            return payload
        except jwt.PyJWTError:
            raise AuthenticationError("Invalid token")

    def authenticate_user(self, username: str, password: str) -> Optional[User]:
        """Authenticate user with username and password"""
        import logging

        logger = logging.getLogger(__name__)

        logger.info(f"Starting authentication for username: {username}")

        try:
            with ModelRegistry.get_session() as session:
                statement = select(User).where(User.username == username)
                user = session.exec(statement).first()

                if not user:
                    logger.warning(f"User not found: {username}")
                    return None

                logger.info(
                    f"User found: {username}, is_active: {user.is_active}, is_staff: {user.is_staff}, is_superuser: {user.is_superuser}"
                )

                # Check password
                logger.info(f"Verifying password for user: {username}")
                password_valid = self.verify_password(password, user.hashed_password)
                logger.info(
                    f"Password verification result for {username}: {password_valid}"
                )

                if not password_valid:
                    logger.warning(f"Invalid password for user: {username}")
                    return None

                if not user.is_active:
                    logger.warning(f"User is not active: {username}")
                    return None

                logger.info(f"Authentication successful for user: {username}")
                return user

        except Exception as e:
            logger.error(f"Authentication error for user {username}: {str(e)}")
            return None

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID"""
        with ModelRegistry.get_session() as session:
            statement = select(User).where(User.id == user_id)
            return session.exec(statement).first()

    def get_user_by_username(self, username: str) -> Optional[User]:
        """Get user by username"""
        with ModelRegistry.get_session() as session:
            statement = select(User).where(User.username == username)
            return session.exec(statement).first()

    def create_user(self, username: str, email: str, password: str, **kwargs) -> User:
        """Create a new user"""
        hashed_password = self.hash_password(password)

        user_data = {
            "username": username,
            "email": email,
            "hashed_password": hashed_password,
            **kwargs,
        }

        user = User(**user_data)

        with ModelRegistry.get_session() as session:
            session.add(user)
            session.commit()
            session.refresh(user)

        return user

    def get_current_user(self, token: str) -> User:
        """Get current user from JWT token"""
        try:
            payload = self.decode_access_token(token)
            user_id: str = payload.get("sub")
            if user_id is None:
                raise AuthenticationError("Invalid token payload")
        except jwt.PyJWTError:
            raise AuthenticationError("Invalid token")

        user = self.get_user_by_id(user_id)
        if user is None:
            raise AuthenticationError("User not found")

        return user


class DefaultAuthBackend(BaseAuthBackend):
    """Default authentication backend implementation"""

    pass


def get_auth_backend() -> BaseAuthBackend:
    """Get the configured authentication backend"""
    try:
        # Handle simple backend names (oauth2, jwt) vs full class paths
        if "." not in settings.AUTH_BACKEND:
            # Simple backend name - use default implementation
            return DefaultAuthBackend()

        import importlib

        module_path, class_name = settings.AUTH_BACKEND.rsplit(".", 1)
        module = importlib.import_module(module_path)
        backend_class = getattr(module, class_name)
        return backend_class()
    except (ImportError, AttributeError, ValueError) as e:
        print(f"Warning: Could not load auth backend {settings.AUTH_BACKEND}: {e}")
        return DefaultAuthBackend()


# Global auth backend instance
auth_backend = get_auth_backend()


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """FastAPI dependency to get current authenticated user"""
    return auth_backend.get_current_user(token)


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """FastAPI dependency to get current active user"""
    if not current_user.is_active:
        raise AuthenticationError("Inactive user")
    return current_user


async def get_current_staff_user(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """FastAPI dependency to get current staff user"""
    if not current_user.is_staff:
        raise PermissionError("Staff access required")
    return current_user


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user),
) -> User:
    """FastAPI dependency to get current superuser"""
    if not current_user.is_superuser:
        raise PermissionError("Superuser access required")
    return current_user


def require_auth(func):
    """Decorator to require authentication for a function"""

    def wrapper(*args, **kwargs):
        # This would be implemented based on the specific use case
        return func(*args, **kwargs)

    return wrapper


class PermissionChecker:
    """Permission checking utility"""

    def __init__(self, permission: str):
        self.permission = permission

    def __call__(self, user: User = Depends(get_current_active_user)) -> User:
        if not user.has_permission(self.permission):
            raise PermissionError(f"Permission '{self.permission}' required")
        return user


def has_permission(permission: str):
    """Create a permission dependency"""
    return PermissionChecker(permission)
