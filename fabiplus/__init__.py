"""
FABI+ Framework - A hybrid API-only Python framework
Combining FastAPI's speed with Django's admin robustness
"""

__version__ = "0.1.0"
__author__ = "FABI+ Team"
__description__ = "Production-ready, modular, extensible API-only framework"

from .conf.settings import settings
from .core.app import create_app
from .core.models import BaseModel

__all__ = ["create_app", "BaseModel", "settings", "__version__"]
