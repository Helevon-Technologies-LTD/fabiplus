"""
ORM abstraction layer for FABI+ framework
Supports SQLModel, SQLAlchemy, and Tortoise ORM
"""

from .base import BaseORMBackend, ORMRegistry
from .sqlalchemy import SQLAlchemyBackend
from .sqlmodel import SQLModelBackend

# from .tortoise import TortoiseBackend  # Disabled for now

__all__ = [
    "BaseORMBackend",
    "ORMRegistry",
    "SQLModelBackend",
    "SQLAlchemyBackend",
    # "TortoiseBackend",  # Disabled for now
]
