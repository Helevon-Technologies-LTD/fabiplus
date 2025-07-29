"""
Base ORM backend interface for FABI+ framework
Defines the contract that all ORM backends must implement
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type


class BaseORMBackend(ABC):
    """
    Abstract base class for ORM backends
    All ORM implementations must inherit from this class
    """

    def __init__(self, project_name: str, database_url: Optional[str] = None):
        self.project_name = project_name
        self.database_url = database_url or f"sqlite:///./{project_name}.db"

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the name of the ORM backend"""
        pass

    @property
    @abstractmethod
    def dependencies(self) -> List[str]:
        """Return list of required dependencies for this ORM"""
        pass

    @property
    @abstractmethod
    def optional_dependencies(self) -> Dict[str, List[str]]:
        """Return dict of optional dependencies (extras)"""
        pass

    @abstractmethod
    def generate_model_code(
        self,
        model_name: str,
        fields: List[Tuple[str, str]],
        app_name: Optional[str] = None,
    ) -> str:
        """Generate model code for this ORM"""
        pass

    @abstractmethod
    def generate_settings_code(self) -> str:
        """Generate settings configuration for this ORM"""
        pass

    @abstractmethod
    def generate_database_init_code(self) -> str:
        """Generate database initialization code"""
        pass

    @abstractmethod
    def generate_migration_config(self, project_dir: Path) -> Dict[str, str]:
        """Generate migration configuration files"""
        pass

    @abstractmethod
    def get_base_model_import(self) -> str:
        """Get the base model import statement"""
        pass

    @abstractmethod
    def get_field_type_mapping(self) -> Dict[str, str]:
        """Get mapping of common field types to ORM-specific types"""
        pass

    @abstractmethod
    def supports_async(self) -> bool:
        """Return True if this ORM supports async operations"""
        pass

    @abstractmethod
    def get_admin_integration_code(self) -> str:
        """Generate admin interface integration code"""
        pass

    def validate_field_type(self, field_type: str) -> bool:
        """Validate if field type is supported by this ORM"""
        mapping = self.get_field_type_mapping()
        return field_type.lower() in mapping

    def get_pyproject_dependencies(self) -> Dict[str, Any]:
        """Get pyproject.toml dependencies section for this ORM"""
        deps = {}

        # Add main dependencies
        for dep in self.dependencies:
            if "=" in dep:
                name, version = dep.split("=", 1)
                deps[name.strip()] = version.strip()
            else:
                deps[dep] = "^0.1.0"  # Default version

        return deps

    def get_pyproject_extras(self) -> Dict[str, List[str]]:
        """Get pyproject.toml extras section for this ORM"""
        return self.optional_dependencies


class ORMRegistry:
    """
    Registry for ORM backends
    Manages available ORM implementations
    """

    _backends: Dict[str, Type[BaseORMBackend]] = {}

    @classmethod
    def register(cls, backend_class: Type[BaseORMBackend]) -> Type[BaseORMBackend]:
        """Register an ORM backend"""
        backend_instance = backend_class("temp", "temp://")
        cls._backends[backend_instance.name] = backend_class
        return backend_class

    @classmethod
    def get_backend(cls, name: str) -> Type[BaseORMBackend]:
        """Get an ORM backend by name"""
        if name not in cls._backends:
            raise ValueError(f"Unknown ORM backend: {name}")
        return cls._backends[name]

    @classmethod
    def list_backends(cls) -> List[str]:
        """List all registered ORM backends"""
        return list(cls._backends.keys())

    @classmethod
    def get_backend_info(cls, name: str) -> Dict[str, Any]:
        """Get information about an ORM backend"""
        backend_class = cls.get_backend(name)
        temp_instance = backend_class("temp", "temp://")

        return {
            "name": temp_instance.name,
            "dependencies": temp_instance.dependencies,
            "optional_dependencies": temp_instance.optional_dependencies,
            "supports_async": temp_instance.supports_async(),
            "field_types": list(temp_instance.get_field_type_mapping().keys()),
        }

    @classmethod
    def validate_backend(cls, name: str) -> bool:
        """Validate if backend exists and is properly configured"""
        try:
            backend_class = cls.get_backend(name)
            temp_instance = backend_class("temp", "temp://")

            # Basic validation
            assert temp_instance.name
            assert temp_instance.dependencies
            assert temp_instance.get_field_type_mapping()

            return True
        except Exception:
            return False


# Decorator for registering ORM backends
def register_orm_backend(cls: Type[BaseORMBackend]) -> Type[BaseORMBackend]:
    """Decorator to register an ORM backend"""
    return ORMRegistry.register(cls)
