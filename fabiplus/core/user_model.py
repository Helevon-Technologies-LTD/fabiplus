"""
FABI+ Framework User Model
Separate module to prevent circular imports and metadata conflicts
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import CHAR, TypeDecorator
from sqlmodel import Field, SQLModel


class GUID(TypeDecorator):
    """Platform-independent GUID type."""

    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                return "%.32x" % value.int

    def process_result_value(self, value, _dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value


class User(SQLModel, table=True):
    """Default User model for authentication"""

    __tablename__ = "users"

    # Primary key and timestamps (copied from BaseModel to avoid circular import)
    id: Optional[uuid.UUID] = Field(
        default_factory=uuid.uuid4,
        sa_column=Column(GUID(), primary_key=True, default=uuid.uuid4),
    )

    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), server_default=func.now()),
    )

    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
        ),
    )

    # User-specific fields
    username: str = Field(unique=True, index=True, max_length=150)
    email: str = Field(unique=True, index=True, max_length=254)
    first_name: Optional[str] = Field(default="", max_length=150)
    last_name: Optional[str] = Field(default="", max_length=150)
    is_active: bool = Field(default=True)
    is_staff: bool = Field(default=False)
    is_superuser: bool = Field(default=False)
    hashed_password: str = Field(max_length=128)
    last_login: Optional[datetime] = Field(default=None)

    def __str__(self):
        return self.username

    @property
    def full_name(self) -> str:
        """Get user's full name"""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_authenticated(self) -> bool:
        """Check if user is authenticated"""
        return True

    def has_permission(self, _permission: str) -> bool:
        """Check if user has a specific permission"""
        # For now, superusers have all permissions
        return self.is_superuser
