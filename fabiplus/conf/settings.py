"""
FABI+ Framework Settings
Pydantic-based settings with .env support and custom overrides
"""

from typing import List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class FABIPlusSettings(BaseSettings):
    """
    Main settings class for FABI+ framework
    Supports .env files and custom settings.py overrides
    """

    # Application Settings
    APP_NAME: str = Field(default="FABI+ API", description="Application name")
    APP_VERSION: str = Field(default="0.1.0", description="Application version")
    DEBUG: bool = Field(default=False, description="Debug mode")
    ENVIRONMENT: str = Field(
        default="development", description="Environment (development, production, test)"
    )

    # Server Settings
    HOST: str = Field(default="127.0.0.1", description="Server host")
    PORT: int = Field(default=8000, description="Server port")
    RELOAD: bool = Field(default=True, description="Auto-reload on code changes")

    # Database Settings
    DATABASE_URL: str = Field(
        default="sqlite:///./fabiplus.db", description="Database connection URL"
    )
    DATABASE_ECHO: bool = Field(default=False, description="Echo SQL queries")

    # Security Settings
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="Secret key for JWT and other cryptographic operations",
    )
    ALGORITHM: str = Field(default="HS256", description="JWT algorithm")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=30, description="JWT token expiration"
    )

    # CORS Settings
    CORS_ORIGINS: List[str] = Field(default=["*"], description="Allowed CORS origins")
    CORS_CREDENTIALS: bool = Field(
        default=True, description="Allow credentials in CORS"
    )
    CORS_METHODS: List[str] = Field(default=["*"], description="Allowed CORS methods")
    CORS_HEADERS: List[str] = Field(default=["*"], description="Allowed CORS headers")

    # Authentication Settings
    AUTH_BACKEND: str = Field(
        default="fabiplus.core.auth.DefaultAuthBackend",
        description="Custom authentication backend class path",
    )
    AUTH_REQUIRED_GLOBALLY: bool = Field(
        default=False, description="Require authentication for all endpoints by default"
    )

    # Admin Settings
    ADMIN_ENABLED: bool = Field(default=True, description="Enable admin interface")
    ADMIN_PREFIX: str = Field(default="/admin", description="Admin URL prefix")
    ADMIN_UI_ENABLED: bool = Field(default=True, description="Enable admin web UI")
    ADMIN_TEMPLATES_DIR: str = Field(
        default="templates/admin", description="Admin templates directory"
    )
    ADMIN_STATIC_DIR: str = Field(
        default="static/admin", description="Admin static files directory"
    )
    ADMIN_ROUTES_IN_DOCS: bool = Field(
        default=False,
        description="Show admin routes in API documentation (/docs, /redoc)",
    )

    # API Settings
    API_PREFIX: str = Field(default="/api", description="API URL prefix")
    API_VERSION: str = Field(default="v1", description="API version")

    # Pagination Settings
    DEFAULT_PAGE_SIZE: int = Field(
        default=20, description="Default pagination page size"
    )
    MAX_PAGE_SIZE: int = Field(default=100, description="Maximum pagination page size")

    # Caching Settings
    CACHE_BACKEND: str = Field(
        default="memory", description="Cache backend (memory, redis, file)"
    )
    CACHE_TTL: int = Field(default=300, description="Default cache TTL in seconds")
    REDIS_URL: Optional[str] = Field(default=None, description="Redis connection URL")

    # Logging Settings
    LOG_LEVEL: str = Field(default="INFO", description="Logging level")
    LOG_FORMAT: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log format",
    )

    # App Settings
    INSTALLED_APPS: List[str] = Field(
        default=[], description="List of installed app module paths"
    )

    # Caching Settings
    CACHE_BACKEND: str = Field(
        default="memory", description="Cache backend: 'memory' or 'redis'"
    )
    CACHE_TTL: int = Field(default=300, description="Default cache TTL in seconds")
    REDIS_URL: Optional[str] = Field(
        default=None, description="Redis connection URL for caching"
    )

    # Plugin Settings
    INSTALLED_PLUGINS: List[str] = Field(
        default=[], description="List of installed plugin module paths"
    )

    # Custom Settings Override
    CUSTOM_SETTINGS_MODULE: Optional[str] = Field(
        default=None,
        description="Path to custom settings module",
        env="FABIPLUS_SETTINGS",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._load_custom_settings()

    def _load_custom_settings(self):
        """Load custom settings from CUSTOM_SETTINGS_MODULE if specified"""
        import sys
        from pathlib import Path

        # Try to auto-detect project settings
        custom_module_path = self.CUSTOM_SETTINGS_MODULE

        if not custom_module_path:
            # Auto-detect project settings in common locations
            try:
                current_dir = Path.cwd()

                # Check if we're in a FABI+ project directory
                possible_settings = [
                    current_dir
                    / current_dir.name
                    / "settings.py",  # project/project/settings.py
                    current_dir / "settings.py",  # project/settings.py
                ]

                # If we're in the framework directory, look for testproject
                if (
                    current_dir.name == "new_fabi"
                    and (current_dir / "testproject").exists()
                ):
                    testproject_dir = current_dir / "testproject"
                    possible_settings.extend(
                        [
                            testproject_dir / "testproject" / "settings.py",
                            testproject_dir / "settings.py",
                        ]
                    )

                for settings_file in possible_settings:
                    if settings_file.exists():
                        # Convert file path to module path
                        if settings_file.parent.name == settings_file.stem:
                            # project/project/settings.py -> project.settings
                            custom_module_path = f"{settings_file.parent.name}.settings"
                        else:
                            # project/settings.py -> settings
                            custom_module_path = settings_file.stem

                        # Add the project directory to Python path
                        project_dir = (
                            settings_file.parent.parent
                            if settings_file.parent.name == settings_file.stem
                            else settings_file.parent
                        )
                        if str(project_dir) not in sys.path:
                            sys.path.insert(0, str(project_dir))
                        break
            except OSError:
                # If we can't get current directory, skip auto-detection
                pass

        if custom_module_path:
            try:
                import importlib

                # Add current directory to Python path
                try:
                    current_dir = str(Path.cwd())
                    if current_dir not in sys.path:
                        sys.path.insert(0, current_dir)
                except OSError:
                    # If we can't get current directory, skip path modification
                    pass

                custom_module = importlib.import_module(custom_module_path)

                # Override settings with custom module attributes
                for attr_name in dir(custom_module):
                    if not attr_name.startswith("_") and hasattr(self, attr_name):
                        setattr(self, attr_name, getattr(custom_module, attr_name))

            except ImportError as e:
                print(
                    f"Warning: Could not import custom settings module {custom_module_path}: {e}"
                )
            except Exception as e:
                print(f"Warning: Error loading custom settings: {e}")


# Global settings instance (lazy initialization)
_settings = None


def get_settings() -> FABIPlusSettings:
    """Get the global settings instance"""
    global _settings
    if _settings is None:
        _settings = FABIPlusSettings()
    return _settings


# Convenience access to settings
settings = get_settings()


def reload_settings():
    """Reload settings (useful for testing)"""
    global _settings, settings
    _settings = None  # Reset the cached settings
    _settings = FABIPlusSettings()  # Create new instance
    settings = _settings  # Update the convenience variable
    return settings
