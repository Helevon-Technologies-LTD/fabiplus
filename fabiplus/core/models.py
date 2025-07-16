"""
FABI+ Framework Base Models
SQLModel-based models with automatic table naming, UUID primary keys, and timestamps
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Type

from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import CHAR, TypeDecorator
from sqlmodel import Field, Session, SQLModel, create_engine

from ..conf.settings import settings


class GUID(TypeDecorator):
    """Platform-independent GUID type for SQLAlchemy"""

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

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            else:
                return value


class BaseModel(SQLModel):
    """
    Base model for all FABI+ models
    Provides UUID primary key, timestamps, and automatic table naming
    """

    # Use Field without sa_column to avoid column reuse conflicts
    # SQLModel will create the columns automatically
    id: Optional[uuid.UUID] = Field(default_factory=uuid.uuid4, primary_key=True)

    created_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: Optional[datetime] = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {datetime: lambda v: v.isoformat(), uuid.UUID: lambda v: str(v)}

    @classmethod
    def get_table_name(cls) -> str:
        """
        Generate table name from class name
        Converts CamelCase to snake_case
        """
        name = cls.__name__
        # Convert CamelCase to snake_case
        import re

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    def to_dict(self) -> Dict[str, Any]:
        """Convert model instance to dictionary"""
        result = {}
        for column in self.__table__.columns:
            value = getattr(self, column.name)
            if isinstance(value, datetime):
                result[column.name] = value.isoformat()
            elif isinstance(value, uuid.UUID):
                result[column.name] = str(value)
            else:
                result[column.name] = value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create model instance from dictionary"""
        return cls(**data)


class ModelRegistry:
    """
    Registry for all models in the application
    Tracks models for auto-API generation and admin interface
    """

    _models: Dict[str, Type[BaseModel]] = {}
    _engine = None

    @classmethod
    def register(cls, model_class: Type[BaseModel]):
        """Register a model class"""
        model_name = model_class.__name__.lower()

        # Check if model is already registered
        if model_name in cls._models:
            # If it's the same class, just return it
            if cls._models[model_name] is model_class:
                return model_class
            else:
                # Different class with same name - this could be a problem
                print(
                    f"Warning: Model '{model_name}' is already registered with a different class"
                )

        cls._models[model_name] = model_class
        return model_class

    @classmethod
    def get_model(cls, model_name: str) -> Optional[Type[BaseModel]]:
        """Get a registered model by name"""
        return cls._models.get(model_name.lower())

    @classmethod
    def get_all_models(cls) -> Dict[str, Type[BaseModel]]:
        """Get all registered models"""
        return cls._models.copy()

    @classmethod
    def get_model_names(cls) -> List[str]:
        """Get all registered model names"""
        return list(cls._models.keys())

    @classmethod
    def create_engine(cls):
        """Create database engine"""
        if cls._engine is None:
            cls._engine = create_engine(
                settings.DATABASE_URL, echo=settings.DATABASE_ECHO
            )
        return cls._engine

    @classmethod
    def create_tables(cls):
        """Create all registered model tables"""
        try:
            # Discover models first
            cls.discover_models()

            engine = cls.create_engine()
            SQLModel.metadata.create_all(engine)

        except Exception as e:
            # If there's a metadata conflict, try to clear and recreate
            if "already assigned" in str(e):
                print(f"Metadata conflict detected: {e}")
                print("Attempting to clear metadata and recreate...")

                # Clear the metadata and model registry
                SQLModel.metadata.clear()
                cls._models.clear()

                # Re-register the built-in User model (defined at the end of this file)
                # We'll re-register it after clearing
                user_model = None
                for obj in globals().values():
                    if (
                        hasattr(obj, "__name__")
                        and obj.__name__ == "User"
                        and hasattr(obj, "__table__")
                    ):
                        user_model = obj
                        break

                if user_model:
                    cls.register(user_model)

                # Re-discover models (this will re-add them to metadata)
                cls.discover_models()

                # Try creating tables again
                engine = cls.create_engine()
                SQLModel.metadata.create_all(engine)
            else:
                raise

    @classmethod
    def get_session(cls) -> Session:
        """Get database session"""
        engine = cls.create_engine()
        return Session(engine)

    @classmethod
    def discover_models(cls):
        """Discover and load all models from installed apps"""
        import importlib
        import sys
        from pathlib import Path

        from ..conf.settings import settings

        print(f"Discovering models from apps: {settings.INSTALLED_APPS}")

        # Keep track of imported modules to avoid duplicates
        imported_modules = set()

        # Import models from all installed apps
        for app_name in settings.INSTALLED_APPS:
            try:
                # Convert app path to module path
                if app_name.startswith("apps."):
                    # Keep the full path for apps under apps/ directory
                    module_path = f"{app_name}.models"
                else:
                    # For apps in root directory
                    module_path = f"{app_name}.models"

                # Skip if already imported
                if module_path in imported_modules:
                    print(f"Skipping already imported module: {module_path}")
                    continue

                print(f"Trying to import: {module_path}")

                # Add current directory to path if not already there
                current_dir = str(Path.cwd())
                if current_dir not in sys.path:
                    sys.path.insert(0, current_dir)

                # Check if module is already in sys.modules
                if module_path in sys.modules:
                    print(f"Module {module_path} already loaded, skipping reload")
                    imported_modules.add(module_path)
                    continue

                # Store current models count to detect new registrations
                models_before = len(cls._models)

                # Import the models module
                try:
                    importlib.import_module(module_path)
                    models_after = len(cls._models)
                    new_models = models_after - models_before
                    print(
                        f"Successfully imported models from {app_name} ({new_models} new models)"
                    )
                    imported_modules.add(module_path)
                except Exception as import_error:
                    # If there's a metadata conflict, it might be due to duplicate model definitions
                    if "already assigned" in str(import_error):
                        print(f"Skipping {app_name} due to duplicate model definitions")
                        imported_modules.add(module_path)
                    else:
                        raise import_error

            except ImportError as e:
                # Skip apps without models
                if "No module named" not in str(e):
                    print(f"Warning: Could not import models from {app_name}: {e}")
                else:
                    print(f"No models module found for {app_name}")
            except Exception as e:
                print(f"Warning: Error loading models from {app_name}: {e}")

        print(f"Total registered models: {len(cls._models)}")
        try:
            model_names = list(cls._models.keys())
            print(f"Registered model names: {model_names}")
        except Exception as e:
            print(f"Error getting model names: {e}")

    @classmethod
    def get_metadata(cls):
        """Get SQLModel metadata"""
        return SQLModel.metadata


def register_model(model_class: Type[BaseModel]):
    """Decorator to register a model"""
    return ModelRegistry.register(model_class)


# Import and register core models from separate modules to prevent conflicts
try:
    from .user_model import User

    # Register the User model only once
    if "user" not in ModelRegistry._models:
        ModelRegistry.register(User)
except ImportError:
    # Fallback if user_model module is not available
    User = None

# Import and register Activity model
try:
    from .activity import Activity

    # Register the Activity model only once
    if "activity" not in ModelRegistry._models:
        ModelRegistry.register(Activity)
except ImportError:
    # Fallback if activity module is not available
    Activity = None

# Import and register permission models
try:
    from .permissions.models import (
        FieldPermission,
        GroupPermission,
        ModelPermission,
        PermissionAuditLog,
        PermissionTemplate,
        Role,
        RolePermission,
        RowPermission,
        UserPermission,
    )

    # Register permission models
    permission_models = [
        Role,
        UserPermission,
        GroupPermission,
        RolePermission,
        ModelPermission,
        FieldPermission,
        RowPermission,
        PermissionTemplate,
        PermissionAuditLog,
    ]

    for model in permission_models:
        model_name = model.__name__.lower()
        if model_name not in ModelRegistry._models:
            ModelRegistry.register(model)

except ImportError as e:
    print(f"Warning: Could not import permission models: {e}")
    # Permission models are optional
