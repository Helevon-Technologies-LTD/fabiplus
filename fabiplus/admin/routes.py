"""
FABI+ Framework Admin Routes
API endpoints for admin interface functionality
"""

import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, func, select

from ..conf.settings import settings
from ..core.auth import get_current_staff_user, get_current_superuser
from ..core.models import ModelRegistry, User
from ..core.views import FilterParams, GenericAPIView, PaginationParams, SortParams

# Module-level dependency instances to avoid B008 warnings
StaffUserDep = Depends(get_current_staff_user)
SuperUserDep = Depends(get_current_superuser)
PaginationDep = Depends()
FilterDep = Depends()
SortDep = Depends()
QueryDep = Query(None, description="Search term")


class AdminView(GenericAPIView):
    """
    Admin-specific view with additional functionality
    """

    def get_model_info(self) -> Dict[str, Any]:
        """Get model metadata for admin interface"""
        # Import types for field analysis
        # import typing  # Currently unused
        # from datetime import date, datetime  # Currently unused
        # from decimal import Decimal  # Currently unused
        # from typing import get_args, get_origin  # Currently unused

        fields = []

        for field_name, field_info in self.model.model_fields.items():
            # Handle Pydantic 2 FieldInfo compatibility
            field_annotation = getattr(
                field_info, "annotation", getattr(field_info, "type_", str)
            )
            field_type_str = str(field_annotation)

            # Check if field is required (Pydantic 2 compatibility)
            is_required = True
            if hasattr(field_info, "is_required"):
                is_required = field_info.is_required()
            elif hasattr(field_info, "required"):
                is_required = field_info.required
            else:
                # Fallback: check if default is PydanticUndefined or similar
                default_val = getattr(field_info, "default", None)
                is_required = (
                    default_val is None or str(default_val) == "PydanticUndefined"
                )

            # Get default value
            default_val = getattr(field_info, "default", None)
            if default_val is not None and str(default_val) in [
                "PydanticUndefined",
                "<PydanticUndefined>",
            ]:
                default_val = None

            # Get description
            description = None
            if hasattr(field_info, "description"):
                description = field_info.description
            elif hasattr(field_info, "field_info") and field_info.field_info:
                description = getattr(field_info.field_info, "description", None)

            # Determine proper field type and widget
            widget_type, widget_attrs = self._get_field_widget_info(
                field_name, field_annotation, field_info
            )

            # Check if it's a foreign key field
            is_foreign_key = (
                field_name.endswith("_id") or "foreign_key" in str(field_info).lower()
            )

            # Get relationship info if it's a foreign key
            related_model = None
            if is_foreign_key:
                related_model = self._get_related_model(field_name, field_annotation)

            field_data = {
                "name": field_name,
                "type": field_type_str,
                "widget_type": widget_type,
                "widget_attrs": widget_attrs,
                "required": is_required,
                "default": default_val,
                "description": description,
                "is_foreign_key": is_foreign_key,
                "related_model": related_model,
                "verbose_name": description or field_name.replace("_", " ").title(),
            }
            fields.append(field_data)

        # Get table name safely
        table_name = self.model.__name__.lower()
        if hasattr(self.model, "get_table_name"):
            table_name = self.model.get_table_name()
        elif hasattr(self.model, "__table__") and hasattr(self.model.__table__, "name"):
            table_name = self.model.__table__.name
        elif hasattr(self.model, "__tablename__"):
            table_name = self.model.__tablename__

        return {
            "name": self.model.__name__,
            "table_name": table_name,
            "fields": fields,
            "verbose_name": getattr(self.model, "_verbose_name", self.model.__name__),
            "verbose_name_plural": getattr(
                self.model, "_verbose_name_plural", f"{self.model.__name__}s"
            ),
        }

    def _get_field_widget_info(
        self, field_name: str, field_annotation, field_info
    ) -> tuple[str, dict]:
        """Determine the appropriate widget type and attributes for a field"""
        import uuid
        from datetime import date, datetime
        from decimal import Decimal
        from typing import Union, get_args, get_origin

        widget_attrs = {}

        # Handle Optional types
        origin = get_origin(field_annotation)
        if origin is Union:
            args = get_args(field_annotation)
            # Remove NoneType from Union to get the actual type
            non_none_args = [arg for arg in args if arg is not type(None)]
            if non_none_args:
                field_annotation = non_none_args[0]

        # Check for foreign key fields
        if field_name.endswith("_id"):
            return "select", {"data-foreign-key": True}

        # Boolean fields - check both type and field name patterns
        if (
            field_annotation is bool
            or field_name.startswith("is_")
            or field_name.startswith("has_")
            or field_name.startswith("can_")
            or field_name
            in ["active", "enabled", "published", "featured", "staff", "superuser"]
        ):
            # Generate a nice label from field name
            if field_name.startswith("is_"):
                label = field_name[3:].replace("_", " ").title()
            elif field_name.startswith("has_"):
                label = f"Has {field_name[4:].replace('_', ' ').title()}"
            elif field_name.startswith("can_"):
                label = f"Can {field_name[4:].replace('_', ' ').title()}"
            else:
                label = field_name.replace("_", " ").title()

            return "checkbox", {"class": "form-check-input", "label": label}

        # Date fields - check both type and field name patterns
        if (
            field_annotation is date
            or "date" in field_name.lower()
            or field_name.endswith("_date")
            or field_name in ["birth_date", "date_of_birth", "dob", "birthday"]
        ):
            return "date", {"type": "date"}

        # DateTime fields - check both type and field name patterns
        if (
            field_annotation is datetime
            or "datetime" in field_name.lower()
            or field_name.endswith("_at")
            or field_name.endswith("_time")
            or field_name in ["created_at", "updated_at", "deleted_at", "timestamp"]
        ):
            return "datetime-local", {"type": "datetime-local"}

        # String fields
        if field_annotation is str:
            # Check field name patterns for specific input types
            if field_name in ["email"] or field_name.endswith("_email"):
                return "email", {"type": "email"}
            elif (
                field_name in ["phone", "telephone", "mobile"] or "phone" in field_name
            ):
                return "tel", {"type": "tel"}
            elif field_name in ["url", "website", "link"] or field_name.endswith(
                "_url"
            ):
                return "url", {"type": "url"}
            elif (
                field_name in ["password", "hashed_password"]
                or "password" in field_name
            ):
                return "password", {"type": "password"}
            elif (
                "description" in field_name
                or "notes" in field_name
                or "content" in field_name
                or "text" in field_name
                or "body" in field_name
                or "message" in field_name
            ):
                return "textarea", {"rows": 4}
            else:
                # Get max_length from field info
                max_length = getattr(field_info, "max_length", None)
                if max_length:
                    widget_attrs["maxlength"] = max_length
                return "text", widget_attrs

        # Numeric fields
        if field_annotation is int:
            widget_attrs["type"] = "number"
            if field_name in ["quantity", "stock_quantity"]:
                widget_attrs["min"] = 0
            return "number", widget_attrs

        if field_annotation is float or field_annotation is Decimal:
            widget_attrs.update({"type": "number", "step": "0.01"})
            if field_name in [
                "price",
                "cost_price",
                "total_amount",
                "tax_amount",
                "shipping_amount",
                "unit_price",
                "total_price",
            ]:
                widget_attrs["min"] = 0
            return "number", widget_attrs

        # Date and datetime fields
        if field_annotation is datetime:
            return "datetime-local", {"type": "datetime-local"}

        if field_annotation is date:
            return "date", {"type": "date"}

        # UUID fields
        if field_annotation is uuid.UUID:
            return "text", {
                "pattern": "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
            }

        # Default to text input
        return "text", {}

    def _get_related_model(self, field_name: str, field_annotation):
        """Get the related model for a foreign key field"""
        if not field_name.endswith("_id"):
            return None

        # Try to find the related model by removing '_id' suffix
        base_name = field_name[:-3]  # Remove '_id'

        # Look for the relationship in the model
        if hasattr(self.model, base_name):
            relationship_attr = getattr(self.model, base_name)
            if hasattr(relationship_attr, "property") and hasattr(
                relationship_attr.property, "mapper"
            ):
                return relationship_attr.property.mapper.class_.__name__.lower()

        return None

    def get_field_choices(
        self, field_name: str, session: Session
    ) -> List[Dict[str, Any]]:
        """Get choices for a specific field (for dropdowns)"""
        if not hasattr(self.model, field_name):
            return []

        # For foreign key fields, return related objects
        # field = getattr(self.model, field_name)  # Currently unused

        # This is a simplified implementation
        # In a real implementation, you'd inspect the field type and relationships
        query = select(self.model)
        results = session.exec(query).all()

        return [{"value": str(item.id), "label": str(item)} for item in results]

    def bulk_delete(self, ids: List[uuid.UUID], session: Session) -> Dict[str, Any]:
        """Bulk delete objects"""
        try:
            query = select(self.model).where(self.model.id.in_(ids))
            items = session.exec(query).all()

            deleted_count = len(items)

            for item in items:
                session.delete(item)

            session.commit()

            return {
                "message": f"Successfully deleted {deleted_count} items",
                "deleted_count": deleted_count,
            }

        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error during bulk delete: {str(e)}",
            )


def create_admin_router() -> APIRouter:
    """Create admin API router with all admin endpoints"""

    router = APIRouter(
        prefix=f"{settings.ADMIN_PREFIX}/api",  # API routes under /admin/api/
        tags=["Admin"],
        include_in_schema=settings.ADMIN_ROUTES_IN_DOCS,  # Show in docs based on setting
    )

    @router.get("/", response_model=Dict[str, Any])
    async def admin_dashboard(current_user: User = StaffUserDep):
        """Admin dashboard with overview statistics"""

        models = ModelRegistry.get_all_models()
        dashboard_data = {
            "user": {
                "username": current_user.username,
                "is_superuser": current_user.is_superuser,
                "is_staff": current_user.is_staff,
            },
            "models": [],
            "statistics": {},
        }

        with ModelRegistry.get_session() as session:
            for model_name, model_class in models.items():
                # Get count for each model
                count_query = select(func.count()).select_from(model_class.__table__)
                count = session.exec(count_query).one()

                model_info = {
                    "name": model_name,
                    "verbose_name": getattr(
                        model_class, "_verbose_name", model_class.__name__
                    ),
                    "count": count,
                    "url": f"{settings.ADMIN_PREFIX}/{model_name}/",
                }
                dashboard_data["models"].append(model_info)
                dashboard_data["statistics"][model_name] = count

        return dashboard_data

    @router.get("/models/", response_model=List[Dict[str, Any]])
    async def list_models(current_user: User = StaffUserDep):
        """List all available models"""

        models = ModelRegistry.get_all_models()
        model_list = []

        for model_name, model_class in models.items():
            admin_view = AdminView(model_class)
            model_info = admin_view.get_model_info()
            model_info["url"] = f"{settings.ADMIN_PREFIX}/{model_name}/"
            model_list.append(model_info)

        return model_list

    @router.get("/{model_name}/", response_model=Dict[str, Any])
    async def admin_model_list(
        model_name: str,
        pagination: PaginationParams = PaginationDep,
        filters: FilterParams = FilterDep,
        sorting: SortParams = SortDep,
        current_user: User = StaffUserDep,
    ):
        """List objects for a specific model in admin interface"""

        model_class = ModelRegistry.get_model(model_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        admin_view = AdminView(model_class)

        # Get model info
        model_info = admin_view.get_model_info()

        # Get paginated results
        results = admin_view.list(
            pagination=pagination,
            filters=filters,
            sorting=sorting,
            current_user=current_user,
        )

        return {"model_info": model_info, "results": results}

    @router.get("/{model_name}/{item_id}/", response_model=Dict[str, Any])
    async def admin_model_detail(
        model_name: str,
        item_id: uuid.UUID,
        current_user: User = StaffUserDep,
    ):
        """Get detailed view of a specific object"""

        model_class = ModelRegistry.get_model(model_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        admin_view = AdminView(model_class)

        # Get model info
        model_info = admin_view.get_model_info()

        # Get object data
        object_data = admin_view.retrieve(item_id, current_user=current_user)

        return {"model_info": model_info, "object": object_data}

    @router.post("/{model_name}/", response_model=Dict[str, Any])
    async def admin_model_create(
        model_name: str,
        data: Dict[str, Any],
        current_user: User = StaffUserDep,
    ):
        """Create new object via admin interface"""

        model_class = ModelRegistry.get_model(model_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        admin_view = AdminView(model_class)
        return admin_view.create(data, current_user=current_user)

    @router.put("/{model_name}/{item_id}/", response_model=Dict[str, Any])
    async def admin_model_update(
        model_name: str,
        item_id: uuid.UUID,
        data: Dict[str, Any],
        current_user: User = StaffUserDep,
    ):
        """Update object via admin interface"""

        model_class = ModelRegistry.get_model(model_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        admin_view = AdminView(model_class)
        return admin_view.update(item_id, data, current_user=current_user)

    @router.delete("/{model_name}/{item_id}/", response_model=Dict[str, str])
    async def admin_model_delete(
        model_name: str,
        item_id: uuid.UUID,
        current_user: User = StaffUserDep,
    ):
        """Delete object via admin interface"""

        model_class = ModelRegistry.get_model(model_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        admin_view = AdminView(model_class)
        return admin_view.delete(item_id, current_user=current_user)

    @router.post("/{model_name}/bulk-delete/", response_model=Dict[str, Any])
    async def admin_bulk_delete(
        model_name: str,
        ids: List[uuid.UUID],
        current_user: User = SuperUserDep,
    ):
        """Bulk delete objects (superuser only)"""

        model_class = ModelRegistry.get_model(model_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        admin_view = AdminView(model_class)

        with ModelRegistry.get_session() as session:
            return admin_view.bulk_delete(ids, session)

    @router.get(
        "/{model_name}/field-choices/{field_name}/", response_model=List[Dict[str, Any]]
    )
    async def admin_field_choices(
        model_name: str,
        field_name: str,
        search: Optional[str] = QueryDep,
        current_user: User = StaffUserDep,
    ):
        """Get choices for a specific field (for dropdowns)"""

        model_class = ModelRegistry.get_model(model_name)
        if not model_class:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Model '{model_name}' not found",
            )

        admin_view = AdminView(model_class)

        with ModelRegistry.get_session() as session:
            choices = admin_view.get_field_choices(field_name, session)

            # Apply search filter if provided
            if search:
                choices = [
                    choice
                    for choice in choices
                    if search.lower() in choice["label"].lower()
                ]

            return choices

    return router


# Global admin router instance
admin_router = create_admin_router()

# Create main admin router that includes both UI and API
main_admin_router = APIRouter()

# Include API router at /admin/api/ FIRST (more specific routes should come first)
main_admin_router.include_router(
    admin_router, tags=["admin-api"], include_in_schema=settings.ADMIN_ROUTES_IN_DOCS
)

# Include UI router at /admin/ if enabled (broader routes should come after specific ones)
if settings.ADMIN_UI_ENABLED:
    try:
        from .ui import ui_router

        main_admin_router.include_router(
            ui_router,
            prefix=settings.ADMIN_PREFIX,
            tags=["admin-ui"],
            include_in_schema=settings.ADMIN_ROUTES_IN_DOCS,
        )
    except ImportError:
        pass  # UI router not available
