"""
FABI+ Framework Auto API Generation
Automatically generates CRUD endpoints for registered models
"""

import uuid
from typing import Any, Dict, List, Type

from fastapi import APIRouter, Depends, status
from pydantic import create_model
from sqlmodel import Session

from ..conf.settings import settings
from ..core.auth import User, get_current_active_user
from ..core.models import BaseModel, ModelRegistry
from ..core.permissions.models import PermissionAction
from ..core.permissions.service import require_model_permission
from ..core.views import (
    AuthenticatedGenericAPIView,
    FilterParams,
    GenericAPIView,
    PaginatedResponse,
    PaginationParams,
    SortParams,
)


class APIGenerator:
    """
    Generates CRUD API endpoints for registered models
    """

    def __init__(self):
        self.routers: Dict[str, APIRouter] = {}

    def create_pydantic_model(
        self, model_class: Type[BaseModel], exclude_fields: List[str] = None
    ):
        """Create a Pydantic model for API input/output"""
        from typing import get_type_hints

        from pydantic import create_model

        if exclude_fields is None:
            exclude_fields = []

        # Get model fields
        fields = {}
        type_hints = get_type_hints(model_class)

        # Get model fields (handle different Pydantic versions)
        model_fields = getattr(model_class, "__fields__", None) or getattr(
            model_class, "model_fields", {}
        )

        for field_name, field_info in model_fields.items():
            if field_name not in exclude_fields:
                # Handle different Pydantic field info structures
                field_type = type_hints.get(field_name)
                if field_type is None:
                    # Try different ways to get the type
                    field_type = getattr(field_info, "type_", None)
                    if field_type is None:
                        field_type = getattr(field_info, "annotation", str)

                # Get default value
                default_value = getattr(field_info, "default", ...)
                if default_value is ...:
                    default_value = None

                fields[field_name] = (field_type, default_value)

        # Create dynamic Pydantic model
        model_name = f"{model_class.__name__}Schema"
        return create_model(model_name, **fields)

    def create_response_model(self, model_class: Type[BaseModel]):
        """Create a Pydantic model for API responses"""
        # For responses, include all fields
        return self.create_pydantic_model(model_class, exclude_fields=[])

    def generate_model_router(
        self, model_name: str, model_class: Type[BaseModel]
    ) -> APIRouter:
        """Generate router for a specific model"""

        # Get app name and proper prefix
        app_name, prefix = self._get_app_info_for_model(model_class)

        # Try to get custom tags from model's app views
        custom_tags = self._get_custom_tags_for_model(model_name, model_class)

        # Get verbose name from model config or use title case as fallback
        if not custom_tags:
            verbose_name = (
                getattr(model_class.Config, "_verbose_name_plural", None)
                if hasattr(model_class, "Config")
                else None
            )
            if not verbose_name:
                verbose_name = model_name.title()
            custom_tags = [verbose_name]

        router = APIRouter(prefix=prefix, tags=custom_tags)

        # Generate Pydantic schemas for the model
        create_schema = self.create_pydantic_model(
            model_class, exclude_fields=["id", "created_at", "updated_at"]
        )
        update_schema = self.create_pydantic_model(
            model_class, exclude_fields=["id", "created_at", "updated_at"]
        )
        response_schema = self.create_response_model(model_class)

        # Create view instance - always use authenticated view for core models
        is_core_model = app_name == "core" or model_name in ["user", "activity"]
        if settings.AUTH_REQUIRED_GLOBALLY or is_core_model:
            view = AuthenticatedGenericAPIView(model_class)
        else:
            view = GenericAPIView(model_class)

        # List endpoint
        if isinstance(view, AuthenticatedGenericAPIView):

            @router.get("/", response_model=PaginatedResponse)
            async def list_items(
                session: Session = Depends(ModelRegistry.get_session),
                pagination: PaginationParams = Depends(),
                filters: FilterParams = Depends(),
                sorting: SortParams = Depends(),
                current_user: User = Depends(get_current_active_user),
            ):
                """List all items with pagination, filtering, and sorting"""
                return view.list(
                    session, pagination, filters, sorting, current_user=current_user
                )

        else:

            @router.get("/", response_model=PaginatedResponse)
            async def list_items(
                session: Session = Depends(ModelRegistry.get_session),
                pagination: PaginationParams = Depends(),
                filters: FilterParams = Depends(),
                sorting: SortParams = Depends(),
            ):
                """List all items with pagination, filtering, and sorting"""
                return view.list(session, pagination, filters, sorting)

        # Retrieve endpoint
        if isinstance(view, AuthenticatedGenericAPIView):

            @router.get("/{item_id}", response_model=response_schema)
            async def retrieve_item(
                item_id: uuid.UUID,
                session: Session = Depends(ModelRegistry.get_session),
                current_user: User = Depends(get_current_active_user),
            ):
                """Retrieve a specific item by ID"""
                return view.retrieve(item_id, session, current_user=current_user)

        else:

            @router.get("/{item_id}", response_model=response_schema)
            async def retrieve_item(
                item_id: uuid.UUID,
                session: Session = Depends(ModelRegistry.get_session),
            ):
                """Retrieve a specific item by ID"""
                return view.retrieve(item_id, session)

        # Create endpoint
        if isinstance(view, AuthenticatedGenericAPIView):

            def create_endpoint_func(
                item_data: create_schema,
                session: Session = Depends(ModelRegistry.get_session),
                current_user: User = Depends(get_current_active_user),
            ):
                """Create a new item"""
                return view.create(item_data.dict(), session, current_user=current_user)

        else:

            def create_endpoint_func(
                item_data: create_schema,
                session: Session = Depends(ModelRegistry.get_session),
            ):
                """Create a new item"""
                return view.create(item_data.dict(), session)

        create_endpoint_func.__annotations__["item_data"] = create_schema
        router.post(
            "/", response_model=response_schema, status_code=status.HTTP_201_CREATED
        )(create_endpoint_func)

        # Update endpoint
        if isinstance(view, AuthenticatedGenericAPIView):

            def update_endpoint_func(
                item_id: uuid.UUID,
                item_data: update_schema,
                session: Session = Depends(ModelRegistry.get_session),
                current_user: User = Depends(get_current_active_user),
            ):
                """Update an existing item"""
                return view.update(
                    item_id, item_data.dict(), session, current_user=current_user
                )

        else:

            def update_endpoint_func(
                item_id: uuid.UUID,
                item_data: update_schema,
                session: Session = Depends(ModelRegistry.get_session),
            ):
                """Update an existing item"""
                return view.update(item_id, item_data.dict(), session)

        update_endpoint_func.__annotations__["item_data"] = update_schema
        router.put("/{item_id}", response_model=response_schema)(update_endpoint_func)

        # Partial update endpoint
        if isinstance(view, AuthenticatedGenericAPIView):

            def patch_endpoint_func(
                item_id: uuid.UUID,
                item_data: update_schema,
                session: Session = Depends(ModelRegistry.get_session),
                current_user: User = Depends(get_current_active_user),
            ):
                """Partially update an existing item"""
                return view.update(
                    item_id, item_data.dict(), session, current_user=current_user
                )

        else:

            def patch_endpoint_func(
                item_id: uuid.UUID,
                item_data: update_schema,
                session: Session = Depends(ModelRegistry.get_session),
            ):
                """Partially update an existing item"""
                return view.update(item_id, item_data.dict(), session)

        patch_endpoint_func.__annotations__["item_data"] = update_schema
        router.patch("/{item_id}", response_model=response_schema)(patch_endpoint_func)

        # Delete endpoint
        if isinstance(view, AuthenticatedGenericAPIView):

            @router.delete("/{item_id}", response_model=Dict[str, str])
            async def delete_item(
                item_id: uuid.UUID,
                session: Session = Depends(ModelRegistry.get_session),
                current_user: User = Depends(get_current_active_user),
            ):
                """Delete an item"""
                return view.delete(item_id, session, current_user=current_user)

        else:

            @router.delete("/{item_id}", response_model=Dict[str, str])
            async def delete_item(
                item_id: uuid.UUID,
                session: Session = Depends(ModelRegistry.get_session),
            ):
                """Delete an item"""
                return view.delete(item_id, session)

        return router

    def generate_all_routers(self) -> Dict[str, APIRouter]:
        """Generate routers for all registered models"""

        models = ModelRegistry.get_all_models()

        for model_name, model_class in models.items():
            if model_name not in self.routers:
                self.routers[model_name] = self.generate_model_router(
                    model_name, model_class
                )

        return self.routers

    def _get_custom_tags_for_model(
        self, model_name: str, model_class: Type[BaseModel]
    ) -> List[str]:
        """Try to get custom tags from the model's app views"""
        try:
            # Get the app name from the model's module
            module_path = model_class.__module__
            if "apps." in module_path:
                app_name = module_path.split("apps.")[1].split(".")[0]

                # Try to import the app's views module
                import importlib

                views_module_path = f"apps.{app_name}.views"
                views_module = importlib.import_module(views_module_path)

                # Check if there's a router with tags
                if hasattr(views_module, "router") and hasattr(
                    views_module.router, "tags"
                ):
                    return views_module.router.tags

        except (ImportError, AttributeError, IndexError):
            pass

        return None

    def _get_app_info_for_model(self, model_class: Type[BaseModel]) -> tuple[str, str]:
        """Get app name and proper prefix for a model"""
        try:
            # Get the app name from the model's module
            module_path = model_class.__module__
            if "apps." in module_path:
                app_name = module_path.split("apps.")[1].split(".")[0]
                model_name = model_class.__name__.lower()

                # For app models, use app-based prefix
                if app_name != "core":
                    return app_name, f"/{app_name}/{model_name}"
                else:
                    # For core models, use simple prefix
                    return app_name, f"/{model_name}"
            else:
                # For non-app models, use simple prefix
                model_name = model_class.__name__.lower()
                return "core", f"/{model_name}"

        except (AttributeError, IndexError):
            # Fallback to simple prefix
            model_name = model_class.__name__.lower()
            return "unknown", f"/{model_name}"

    def get_main_router(self) -> APIRouter:
        """Get main API router with all model routers included"""

        main_router = APIRouter(prefix=settings.API_PREFIX)

        # First, include custom routers from apps (they take precedence)
        custom_routers = self._discover_custom_routers()
        for app_name, router in custom_routers.items():
            main_router.include_router(router)

        # Generate all model routers (only for models without custom routers)
        self.generate_all_routers()

        # Include auto-generated model routers
        for model_name, router in self.routers.items():
            main_router.include_router(router)

        return main_router

    def _discover_custom_routers(self) -> Dict[str, APIRouter]:
        """Discover custom routers from installed apps"""
        custom_routers = {}

        for app_name in settings.INSTALLED_APPS:
            try:
                # Try to import the app's views module
                import importlib

                views_module_path = f"{app_name}.views"
                views_module = importlib.import_module(views_module_path)

                # Look for a router in the views module
                if hasattr(views_module, "router") and isinstance(
                    views_module.router, APIRouter
                ):
                    custom_routers[app_name] = views_module.router
                    continue

            except ImportError:
                pass

            try:
                # Try to import the app's urls module
                urls_module_path = f"{app_name}.urls"
                urls_module = importlib.import_module(urls_module_path)

                # Look for a router in the urls module
                if hasattr(urls_module, "router") and isinstance(
                    urls_module.router, APIRouter
                ):
                    custom_routers[app_name] = urls_module.router

            except ImportError:
                pass

        return custom_routers


# Global API generator instance
api_generator = APIGenerator()


def get_api_router() -> APIRouter:
    """Get the main API router"""
    return api_generator.get_main_router()


def register_custom_router(router: APIRouter, prefix: str = ""):
    """Register a custom router with the API"""
    main_router = api_generator.get_main_router()
    main_router.include_router(router, prefix=prefix)


class CustomAPIView:
    """
    Base class for custom API views
    Provides utilities for common operations
    """

    def __init__(self, model: Type[BaseModel] = None):
        self.model = model
        if model:
            self.view = GenericAPIView(model)

    def get_router(self) -> APIRouter:
        """Override this method to define custom routes"""
        raise NotImplementedError("Subclasses must implement get_router method")


def create_custom_endpoint(
    path: str,
    methods: list = ["GET"],
    model: Type[BaseModel] = None,
    auth_required: bool = None,
):
    """
    Decorator to create custom endpoints

    Usage:
    @create_custom_endpoint("/custom", methods=["GET", "POST"])
    def my_custom_endpoint():
        return {"message": "Custom endpoint"}
    """

    def decorator(func):
        # This would be implemented to register the custom endpoint
        # For now, just return the function
        return func

    return decorator
