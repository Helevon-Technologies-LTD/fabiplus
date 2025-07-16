"""
FABI+ Framework Generic API Views
Provides CRUD operations with pagination, filtering, and sorting
"""

import uuid
from typing import Any, Dict, List, Optional, Type, Union

from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel as PydanticBaseModel
from sqlmodel import Session, func, select

from ..conf.settings import settings
from .auth import get_current_active_user
from .models import BaseModel, ModelRegistry, User
from .permissions.models import PermissionAction
from .permissions.service import PermissionService


class PaginationParams:
    """Pagination parameters"""

    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number"),
        page_size: int = Query(
            settings.DEFAULT_PAGE_SIZE,
            ge=1,
            le=settings.MAX_PAGE_SIZE,
            description="Page size",
        ),
    ):
        self.page = page
        self.page_size = page_size
        self.offset = (page - 1) * page_size


class FilterParams:
    """Filtering parameters"""

    def __init__(
        self, filters: Optional[str] = Query(None, description="JSON filters")
    ):
        self.filters = {}
        if filters and isinstance(filters, str):
            try:
                import json

                self.filters = json.loads(filters)
            except json.JSONDecodeError:
                pass


class SortParams:
    """Sorting parameters"""

    def __init__(
        self, ordering: Optional[str] = Query(None, description="Ordering field")
    ):
        self.ordering = ordering


class PaginatedResponse(PydanticBaseModel):
    """Paginated response model"""

    count: int
    next: Optional[str] = None
    previous: Optional[str] = None
    results: List[Dict[str, Any]]


class GenericAPIView:
    """
    Generic API view for CRUD operations
    Can be extended for custom behavior
    """

    model: Type[BaseModel] = None
    auth_required: bool = False
    permission_classes: List = []

    def __init__(self, model: Type[BaseModel] = None):
        if model:
            self.model = model

        if not self.model:
            raise ValueError("Model must be specified")

    def get_queryset(self, session: Session, user: Optional[User] = None):
        """Get base queryset - can be overridden for filtering"""
        return select(self.model)

    def apply_filters(self, query, filters: Dict[str, Any]):
        """Apply filters to query"""
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        return query

    def apply_ordering(self, query, ordering: Optional[str]):
        """Apply ordering to query"""
        if not ordering:
            # Default ordering - try different timestamp fields
            if hasattr(self.model, "created_at"):
                return query.order_by(self.model.created_at.desc())
            elif hasattr(self.model, "granted_at"):
                return query.order_by(self.model.granted_at.desc())
            elif hasattr(self.model, "timestamp"):
                return query.order_by(self.model.timestamp.desc())
            elif hasattr(self.model, "id"):
                return query.order_by(self.model.id.desc())
            else:
                return query  # No default ordering

        desc = ordering.startswith("-")
        field_name = ordering.lstrip("-")

        if hasattr(self.model, field_name):
            field = getattr(self.model, field_name)
            if desc:
                query = query.order_by(field.desc())
            else:
                query = query.order_by(field.asc())

        return query

    def list(
        self,
        session: Session = Depends(ModelRegistry.get_session),
        pagination: PaginationParams = Depends(),
        filters: FilterParams = Depends(),
        sorting: SortParams = Depends(),
        current_user: Optional[User] = None,
    ) -> PaginatedResponse:
        """List objects with pagination, filtering, and sorting"""

        # Get base query
        query = self.get_queryset(session, current_user)

        # Apply filters
        if filters.filters:
            query = self.apply_filters(query, filters.filters)

        # Apply ordering
        query = self.apply_ordering(query, sorting.ordering)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        total_count = session.exec(count_query).one()

        # Apply pagination
        paginated_query = query.offset(pagination.offset).limit(pagination.page_size)
        results = session.exec(paginated_query).all()

        # Convert to dict
        results_data = [item.model_dump() for item in results]

        # Calculate pagination links
        next_page = None
        previous_page = None

        if pagination.offset + pagination.page_size < total_count:
            next_page = f"page={pagination.page + 1}"

        if pagination.page > 1:
            previous_page = f"page={pagination.page - 1}"

        return PaginatedResponse(
            count=total_count,
            next=next_page,
            previous=previous_page,
            results=results_data,
        )

    def retrieve(
        self,
        item_id: uuid.UUID,
        session: Session = Depends(ModelRegistry.get_session),
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """Retrieve a single object"""

        query = self.get_queryset(session, current_user)
        query = query.where(self.model.id == item_id)

        item = session.exec(query).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
            )

        return item.model_dump()

    def create(
        self,
        data: Dict[str, Any],
        session: Session = Depends(ModelRegistry.get_session),
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """Create a new object"""

        try:
            # Remove id if present (will be auto-generated)
            data.pop("id", None)
            data.pop("created_at", None)
            data.pop("updated_at", None)

            item = self.model(**data)
            session.add(item)
            session.commit()
            session.refresh(item)

            return item.model_dump()

        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error creating object: {str(e)}",
            )

    def update(
        self,
        item_id: uuid.UUID,
        data: Dict[str, Any],
        session: Session = Depends(ModelRegistry.get_session),
        current_user: Optional[User] = None,
    ) -> Dict[str, Any]:
        """Update an existing object"""

        query = self.get_queryset(session, current_user)
        query = query.where(self.model.id == item_id)

        item = session.exec(query).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
            )

        try:
            # Remove fields that shouldn't be updated
            data.pop("id", None)
            data.pop("created_at", None)

            # Update fields
            for field, value in data.items():
                if hasattr(item, field):
                    setattr(item, field, value)

            session.add(item)
            session.commit()
            session.refresh(item)

            return item.model_dump()

        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error updating object: {str(e)}",
            )

    def delete(
        self,
        item_id: uuid.UUID,
        session: Session = Depends(ModelRegistry.get_session),
        current_user: Optional[User] = None,
    ) -> Dict[str, str]:
        """Delete an object"""

        query = self.get_queryset(session, current_user)
        query = query.where(self.model.id == item_id)

        item = session.exec(query).first()
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Object not found"
            )

        try:
            session.delete(item)
            session.commit()

            return {"message": "Object deleted successfully"}

        except Exception as e:
            session.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Error deleting object: {str(e)}",
            )


class AuthenticatedGenericAPIView(GenericAPIView):
    """Generic API view that requires authentication and checks permissions"""

    auth_required = True

    def _check_permission(self, user: User, action: PermissionAction, session: Session):
        """Check if user has permission for action on this model"""
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )

        model_name = self.model.__name__.lower()
        perm_service = PermissionService(session)

        if not perm_service.has_model_permission(user, model_name, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied: {model_name}.{action.value}",
            )

    def list(self, session: Session, *args, current_user: User = None, **kwargs):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        self._check_permission(current_user, PermissionAction.LIST, session)
        return super().list(session, *args, current_user=current_user, **kwargs)

    def retrieve(self, item_id, session: Session, current_user: User = None):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        self._check_permission(current_user, PermissionAction.READ, session)
        return super().retrieve(item_id, session, current_user=current_user)

    def create(self, data, session: Session, current_user: User = None):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        self._check_permission(current_user, PermissionAction.CREATE, session)
        return super().create(data, session, current_user=current_user)

    def update(self, item_id, data, session: Session, current_user: User = None):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        self._check_permission(current_user, PermissionAction.UPDATE, session)
        return super().update(item_id, data, session, current_user=current_user)

    def delete(self, item_id, session: Session, current_user: User = None):
        if current_user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        self._check_permission(current_user, PermissionAction.DELETE, session)
        return super().delete(item_id, session, current_user=current_user)
