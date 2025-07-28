"""
FABI+ App Configuration System
Django-style app configuration for FABI+ applications
"""

import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Type, cast


class AppConfig:
    """
    Base class for app configuration
    Similar to Django's AppConfig
    """

    name: Optional[str] = None
    verbose_name: Optional[str] = None
    path: Optional[str] = None

    def __init__(self, app_name: str, app_module: Any) -> None:
        self.name = app_name
        self.module = app_module

        if self.verbose_name is None:
            self.verbose_name = app_name.title()

        if hasattr(app_module, "__path__"):
            self.path = app_module.__path__[0]
        elif hasattr(app_module, "__file__"):
            self.path = str(Path(app_module.__file__).parent)

    def ready(self) -> None:
        """
        Override this method in subclasses to perform initialization tasks
        This is called after all apps are loaded
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"


class AppRegistry:
    """
    Registry for all installed apps
    Manages app loading and configuration
    """

    def __init__(self) -> None:
        self.apps: Dict[str, AppConfig] = {}
        self.ready = False

    def populate(self, installed_apps: List[str]) -> None:
        """
        Load and configure all installed apps
        """
        if self.ready:
            return

        for app_name in installed_apps:
            self.load_app(app_name)

        # Call ready() on all apps
        for app_config in self.apps.values():
            app_config.ready()

        self.ready = True

    def load_app(self, app_name: str) -> None:
        """
        Load a single app and its configuration
        """
        try:
            # Import the app module
            app_module = importlib.import_module(app_name)

            # Look for app config
            app_config = self._get_app_config(app_name, app_module)

            # Register the app
            self.apps[app_name] = app_config

        except ImportError as e:
            raise ImportError(f"Could not import app '{app_name}': {e}")

    def _get_app_config(self, app_name: str, app_module: Any) -> AppConfig:
        """
        Get app configuration for an app module
        """
        # Look for apps.py module
        try:
            apps_module = importlib.import_module(f"{app_name}.apps")

            # Look for default_app_config
            if hasattr(apps_module, "default_app_config"):
                config_class_path = apps_module.default_app_config
                module_path, class_name = config_class_path.rsplit(".", 1)
                config_module = importlib.import_module(module_path)
                config_class = cast(Type[AppConfig], getattr(config_module, class_name))
                return config_class(app_name, app_module)

            # Look for AppConfig subclasses
            for attr_name in dir(apps_module):
                attr = getattr(apps_module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, AppConfig)
                    and attr != AppConfig
                ):
                    return attr(app_name, app_module)

        except ImportError:
            pass

        # Default app config
        return AppConfig(app_name, app_module)

    def get_app_config(self, app_name: str) -> Optional[AppConfig]:
        """Get app configuration by name"""
        return self.apps.get(app_name)

    def get_app_configs(self) -> List[AppConfig]:
        """Get all app configurations"""
        return list(self.apps.values())

    def is_installed(self, app_name: str) -> bool:
        """Check if an app is installed"""
        return app_name in self.apps


# Global app registry
apps = AppRegistry()


def get_app_config(app_name: str) -> Optional[AppConfig]:
    """Get app configuration by name"""
    return apps.get_app_config(app_name)


def get_app_configs() -> List[AppConfig]:
    """Get all app configurations"""
    return apps.get_app_configs()


def is_app_installed(app_name: str) -> bool:
    """Check if an app is installed"""
    return apps.is_installed(app_name)
