"""
FABI+ Framework Permission Service
Handles permission checking and role-based access control
"""

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Set

from sqlmodel import Session, select

from ..models import ModelRegistry, User
from .models import (
    FieldPermission,
    ModelPermission,
    PermissionAction,
    PermissionScope,
    Role,
    RolePermission,
    RowPermission,
    UserPermission,
)


class PermissionService:
    """Service for handling permissions and access control"""

    def __init__(self, session: Session):
        self.session = session

    def get_user_permissions(self, user: User) -> Set[str]:
        """Get all permissions for a user (direct + role-based)"""
        permissions = set()

        # Get direct user permissions
        stmt = select(UserPermission).where(
            UserPermission.user_id == user.id, UserPermission.is_active.is_(True)
        )
        user_perms = self.session.exec(stmt).all()

        for perm in user_perms:
            if perm.is_granted:
                permissions.add(f"{perm.permission_id}")

        # Get role-based permissions
        user_roles = self.get_user_roles(user)
        for role in user_roles:
            role_perms = self.get_role_permissions(role)
            permissions.update(role_perms)

        return permissions

    def get_user_roles(self, user: User) -> List[Role]:
        """Get all active roles for a user"""
        # For now, return default roles based on user type
        roles = []

        if user.is_superuser:
            roles.append(
                self._get_or_create_role(
                    "superuser", "Full system access", is_system=True
                )
            )
        elif user.is_staff:
            roles.append(
                self._get_or_create_role("staff", "Staff access", is_system=True)
            )
        else:
            roles.append(
                self._get_or_create_role("user", "Regular user", is_system=True)
            )

        return roles

    def get_role_permissions(self, role: Role) -> Set[str]:
        """Get all permissions for a role"""
        permissions = set()

        # Default permissions based on role name
        if role.name == "superuser":
            permissions.add("*")  # All permissions
        elif role.name == "staff":
            permissions.update(
                [
                    "user.read",
                    "user.list",
                    "admin.access",
                    "activity.read",
                    "activity.list",
                ]
            )
        elif role.name == "user":
            permissions.update(
                ["post.read", "post.list", "category.read", "category.list"]
            )

        return permissions

    def has_permission(self, user: User, action: str, resource: str = None) -> bool:
        """Check if user has permission for action on resource"""

        # Superuser has all permissions
        if user.is_superuser:
            return True

        # Build permission string
        if resource:
            permission_str = f"{resource}.{action}"
        else:
            permission_str = action

        # Get user permissions
        user_permissions = self.get_user_permissions(user)

        # Check for wildcard permission
        if "*" in user_permissions:
            return True

        # Check for exact permission
        if permission_str in user_permissions:
            return True

        # Check for resource wildcard (e.g., "user.*")
        if resource:
            resource_wildcard = f"{resource}.*"
            if resource_wildcard in user_permissions:
                return True

        return False

    def has_model_permission(
        self, user: User, model_name: str, action: PermissionAction
    ) -> bool:
        """Check if user has permission for action on model"""
        return self.has_permission(user, action.value, model_name)

    def has_field_permission(
        self, user: User, model_name: str, field_name: str, action: PermissionAction
    ) -> bool:
        """Check if user has permission for action on specific field"""

        # First check model-level permission
        if not self.has_model_permission(user, model_name, action):
            return False

        # Then check field-level restrictions
        stmt = select(FieldPermission).where(
            FieldPermission.model_name == model_name,
            FieldPermission.field_name == field_name,
            FieldPermission.user_id == user.id,
            FieldPermission.is_active.is_(True),
        )
        field_perm = self.session.exec(stmt).first()

        if field_perm:
            if action == PermissionAction.READ:
                return field_perm.can_read
            elif action == PermissionAction.UPDATE:
                return field_perm.can_write

        # Default to model permission if no field-specific rules
        return True

    def has_row_permission(
        self, user: User, model_name: str, row_id: str, action: PermissionAction
    ) -> bool:
        """Check if user has permission for action on specific row"""

        # First check model-level permission
        if not self.has_model_permission(user, model_name, action):
            return False

        # Then check row-level restrictions
        stmt = select(RowPermission).where(
            RowPermission.model_name == model_name,
            RowPermission.row_id == row_id,
            RowPermission.user_id == user.id,
            RowPermission.is_active.is_(True),
        )
        row_perm = self.session.exec(stmt).first()

        if row_perm:
            if action == PermissionAction.READ:
                return row_perm.can_read
            elif action == PermissionAction.UPDATE:
                return row_perm.can_update
            elif action == PermissionAction.DELETE:
                return row_perm.can_delete

        # Default to model permission if no row-specific rules
        return True

    def _get_or_create_role(
        self, name: str, description: str, is_system: bool = False
    ) -> Role:
        """Get or create a role"""
        stmt = select(Role).where(Role.name == name)
        role = self.session.exec(stmt).first()

        if not role:
            role = Role(
                name=name, description=description, is_system=is_system, is_active=True
            )
            self.session.add(role)
            self.session.commit()
            self.session.refresh(role)

        return role

    def create_default_permissions(self):
        """Create default system permissions"""
        from .models import DEFAULT_PERMISSIONS, DEFAULT_ROLES

        # Create default permissions
        for perm_data in DEFAULT_PERMISSIONS:
            # Check if permission already exists
            # Implementation would go here
            pass

        # Create default roles
        for role_data in DEFAULT_ROLES:
            self._get_or_create_role(
                role_data["name"],
                role_data["description"],
                role_data.get("is_system", False),
            )


def get_permission_service(session: Session = None) -> PermissionService:
    """Get permission service instance"""
    if session is None:
        session = ModelRegistry.get_session()
    return PermissionService(session)


# Permission decorators for FastAPI endpoints
from functools import wraps

from fastapi import Depends, HTTPException, status

from ..auth import get_current_active_user


def require_permission(action: str, resource: str = None):
    """Decorator to require specific permission for endpoint"""

    def decorator(func):
        @wraps(func)
        async def wrapper(
            *args, current_user: User = Depends(get_current_active_user), **kwargs
        ):
            with ModelRegistry.get_session() as session:
                perm_service = PermissionService(session)

                if not perm_service.has_permission(current_user, action, resource):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {resource}.{action}"
                        if resource
                        else f"Permission denied: {action}",
                    )

            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator


def require_model_permission(model_name: str, action: PermissionAction):
    """Decorator to require model-level permission"""

    def decorator(func):
        @wraps(func)
        async def wrapper(
            *args, current_user: User = Depends(get_current_active_user), **kwargs
        ):
            with ModelRegistry.get_session() as session:
                perm_service = PermissionService(session)

                if not perm_service.has_model_permission(
                    current_user, model_name, action
                ):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission denied: {model_name}.{action.value}",
                    )

            return await func(*args, current_user=current_user, **kwargs)

        return wrapper

    return decorator
