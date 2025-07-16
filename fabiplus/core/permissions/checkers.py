"""
Permission checkers for different scopes and levels
"""

from typing import Any, Dict, List, Optional, Type, Union

from sqlmodel import Session, select

from .base import (
    Permission,
    PermissionAction,
    PermissionChecker,
    PermissionContext,
    PermissionScope,
    PermissionSet,
)
from .models import (
    FieldPermission,
    GroupPermission,
    ModelPermission,
    RolePermission,
    RowPermission,
    UserPermission,
)


class ModelPermissionChecker(PermissionChecker):
    """Checker for model-level permissions"""

    def __init__(self, session: Session):
        self.session = session

    async def check_permission(
        self,
        user: Any,
        permission: Union[str, Permission],
        resource: Optional[Any] = None,
        **kwargs,
    ) -> bool:
        """Check model-level permission"""

        if isinstance(permission, str):
            # Parse permission string
            parts = permission.split(":")
            if len(parts) < 2:
                return False
            action = PermissionAction(parts[1])
            model_name = parts[2] if len(parts) > 2 else None
        else:
            action = permission.action
            model_name = permission.resource

        # If no model specified, check if user has global permission
        if not model_name and resource:
            model_name = resource.__class__.__name__

        if not model_name:
            return False

        # Check user permissions
        user_perms = self.session.exec(
            select(ModelPermission).where(
                ModelPermission.user_id == user.id,
                ModelPermission.model_name == model_name,
            )
        ).all()

        for perm in user_perms:
            if perm.has_permission(action):
                return True

        # Check group permissions
        if hasattr(user, "groups"):
            for group in user.groups:
                group_perms = self.session.exec(
                    select(ModelPermission).where(
                        ModelPermission.group_id == group.id,
                        ModelPermission.model_name == model_name,
                    )
                ).all()

                for perm in group_perms:
                    if perm.has_permission(action):
                        return True

        # Check role permissions
        if hasattr(user, "roles"):
            for role in user.roles:
                role_perms = self.session.exec(
                    select(ModelPermission).where(
                        ModelPermission.role_id == role.id,
                        ModelPermission.model_name == model_name,
                    )
                ).all()

                for perm in role_perms:
                    if perm.has_permission(action):
                        return True

        return False

    async def get_user_permissions(
        self,
        user: Any,
        scope: Optional[PermissionScope] = None,
        resource: Optional[str] = None,
    ) -> List[Permission]:
        """Get all model permissions for user"""

        permissions = []

        # Direct user permissions
        query = select(ModelPermission).where(ModelPermission.user_id == user.id)
        if resource:
            query = query.where(ModelPermission.model_name == resource)

        user_perms = self.session.exec(query).all()

        for perm in user_perms:
            # Convert to Permission objects
            for action in [
                PermissionAction.CREATE,
                PermissionAction.READ,
                PermissionAction.UPDATE,
                PermissionAction.DELETE,
                PermissionAction.LIST,
            ]:
                if perm.has_permission(action):
                    permissions.append(
                        Permission(
                            name=f"model:{action}:{perm.model_name}",
                            scope=PermissionScope.MODEL,
                            action=action,
                            resource=perm.model_name,
                        )
                    )

        return permissions


class FieldPermissionChecker(PermissionChecker):
    """Checker for field-level permissions"""

    def __init__(self, session: Session):
        self.session = session

    async def check_permission(
        self,
        user: Any,
        permission: Union[str, Permission],
        resource: Optional[Any] = None,
        **kwargs,
    ) -> bool:
        """Check field-level permission"""

        field_name = kwargs.get("field_name")
        if not field_name:
            return True  # No field restriction

        if isinstance(permission, str):
            parts = permission.split(":")
            if len(parts) < 2:
                return False
            action = PermissionAction(parts[1])
            model_name = parts[2] if len(parts) > 2 else None
        else:
            action = permission.action
            model_name = permission.resource

        if not model_name and resource:
            model_name = resource.__class__.__name__

        if not model_name:
            return False

        # Check field permissions
        field_perms = self.session.exec(
            select(FieldPermission).where(
                FieldPermission.user_id == user.id,
                FieldPermission.model_name == model_name,
                FieldPermission.field_name == field_name,
            )
        ).all()

        for perm in field_perms:
            if perm.has_permission(action):
                return True

        # Check group field permissions
        if hasattr(user, "groups"):
            for group in user.groups:
                group_perms = self.session.exec(
                    select(FieldPermission).where(
                        FieldPermission.group_id == group.id,
                        FieldPermission.model_name == model_name,
                        FieldPermission.field_name == field_name,
                    )
                ).all()

                for perm in group_perms:
                    if perm.has_permission(action):
                        return True

        # If no specific field permission found, check model permission
        model_checker = ModelPermissionChecker(self.session)
        return await model_checker.check_permission(
            user, permission, resource, **kwargs
        )

    async def get_user_permissions(
        self,
        user: Any,
        scope: Optional[PermissionScope] = None,
        resource: Optional[str] = None,
    ) -> List[Permission]:
        """Get all field permissions for user"""

        permissions = []

        query = select(FieldPermission).where(FieldPermission.user_id == user.id)
        if resource:
            query = query.where(FieldPermission.model_name == resource)

        field_perms = self.session.exec(query).all()

        for perm in field_perms:
            for action in [PermissionAction.READ, PermissionAction.UPDATE]:
                if perm.has_permission(action):
                    permissions.append(
                        Permission(
                            name=f"field:{action}:{perm.model_name}.{perm.field_name}",
                            scope=PermissionScope.FIELD,
                            action=action,
                            resource=f"{perm.model_name}.{perm.field_name}",
                        )
                    )

        return permissions


class RowPermissionChecker(PermissionChecker):
    """Checker for row-level permissions"""

    def __init__(self, session: Session):
        self.session = session

    async def check_permission(
        self,
        user: Any,
        permission: Union[str, Permission],
        resource: Optional[Any] = None,
        **kwargs,
    ) -> bool:
        """Check row-level permission"""

        if not resource or not hasattr(resource, "id"):
            return False

        if isinstance(permission, str):
            parts = permission.split(":")
            if len(parts) < 2:
                return False
            action = PermissionAction(parts[1])
            model_name = parts[2] if len(parts) > 2 else None
        else:
            action = permission.action
            model_name = permission.resource

        if not model_name:
            model_name = resource.__class__.__name__

        row_id = str(resource.id)

        # Check ownership first
        if hasattr(resource, "owner_id") and resource.owner_id == user.id:
            return True

        if hasattr(resource, "created_by") and resource.created_by == user.id:
            return True

        # Check explicit row permissions
        row_perms = self.session.exec(
            select(RowPermission).where(
                RowPermission.user_id == user.id,
                RowPermission.model_name == model_name,
                RowPermission.row_id == row_id,
            )
        ).all()

        for perm in row_perms:
            if perm.is_valid and perm.has_permission(action):
                return True

        # Check group row permissions
        if hasattr(user, "groups"):
            for group in user.groups:
                group_perms = self.session.exec(
                    select(RowPermission).where(
                        RowPermission.group_id == group.id,
                        RowPermission.model_name == model_name,
                        RowPermission.row_id == row_id,
                    )
                ).all()

                for perm in group_perms:
                    if perm.is_valid and perm.has_permission(action):
                        return True

        # Fall back to model-level permission
        model_checker = ModelPermissionChecker(self.session)
        return await model_checker.check_permission(
            user, permission, resource, **kwargs
        )

    async def get_user_permissions(
        self,
        user: Any,
        scope: Optional[PermissionScope] = None,
        resource: Optional[str] = None,
    ) -> List[Permission]:
        """Get all row permissions for user"""

        permissions = []

        query = select(RowPermission).where(RowPermission.user_id == user.id)
        if resource:
            query = query.where(RowPermission.model_name == resource)

        row_perms = self.session.exec(query).all()

        for perm in row_perms:
            if perm.is_valid:
                for action in [
                    PermissionAction.READ,
                    PermissionAction.UPDATE,
                    PermissionAction.DELETE,
                ]:
                    if perm.has_permission(action):
                        permissions.append(
                            Permission(
                                name=f"row:{action}:{perm.model_name}#{perm.row_id}",
                                scope=PermissionScope.ROW,
                                action=action,
                                resource=f"{perm.model_name}#{perm.row_id}",
                            )
                        )

        return permissions


class CompositePermissionChecker(PermissionChecker):
    """Composite checker that combines multiple permission levels"""

    def __init__(self, session: Session):
        self.session = session
        self.model_checker = ModelPermissionChecker(session)
        self.field_checker = FieldPermissionChecker(session)
        self.row_checker = RowPermissionChecker(session)

    async def check_permission(
        self,
        user: Any,
        permission: Union[str, Permission],
        resource: Optional[Any] = None,
        **kwargs,
    ) -> bool:
        """Check permission using appropriate checker based on scope"""

        if isinstance(permission, str):
            parts = permission.split(":")
            scope = PermissionScope(parts[0]) if parts else PermissionScope.MODEL
        else:
            scope = permission.scope

        # Route to appropriate checker
        if scope == PermissionScope.ROW:
            return await self.row_checker.check_permission(
                user, permission, resource, **kwargs
            )
        elif scope == PermissionScope.FIELD:
            return await self.field_checker.check_permission(
                user, permission, resource, **kwargs
            )
        elif scope == PermissionScope.MODEL:
            return await self.model_checker.check_permission(
                user, permission, resource, **kwargs
            )
        else:
            # Default to model-level check
            return await self.model_checker.check_permission(
                user, permission, resource, **kwargs
            )

    async def get_user_permissions(
        self,
        user: Any,
        scope: Optional[PermissionScope] = None,
        resource: Optional[str] = None,
    ) -> List[Permission]:
        """Get all permissions for user across all scopes"""

        permissions = []

        if scope is None or scope == PermissionScope.MODEL:
            model_perms = await self.model_checker.get_user_permissions(
                user, scope, resource
            )
            permissions.extend(model_perms)

        if scope is None or scope == PermissionScope.FIELD:
            field_perms = await self.field_checker.get_user_permissions(
                user, scope, resource
            )
            permissions.extend(field_perms)

        if scope is None or scope == PermissionScope.ROW:
            row_perms = await self.row_checker.get_user_permissions(
                user, scope, resource
            )
            permissions.extend(row_perms)

        return permissions

    async def get_user_permission_set(self, user: Any) -> PermissionSet:
        """Get user's permissions as an efficient PermissionSet"""

        permissions = await self.get_user_permissions(user)
        return PermissionSet(permissions)

    async def check_model_access(
        self,
        user: Any,
        model_class: Type,
        action: PermissionAction,
        instance: Optional[Any] = None,
    ) -> bool:
        """Convenient method to check model access"""

        model_name = model_class.__name__

        # Check model-level permission
        model_perm = Permission(
            name=f"model:{action}:{model_name}",
            scope=PermissionScope.MODEL,
            action=action,
            resource=model_name,
        )

        has_model_access = await self.model_checker.check_permission(user, model_perm)

        # If checking specific instance, also check row-level
        if instance and has_model_access:
            row_perm = Permission(
                name=f"row:{action}:{model_name}",
                scope=PermissionScope.ROW,
                action=action,
                resource=model_name,
            )
            return await self.row_checker.check_permission(user, row_perm, instance)

        return has_model_access

    async def filter_queryset(
        self,
        user: Any,
        queryset,
        model_class: Type,
        action: PermissionAction = PermissionAction.READ,
    ):
        """Filter queryset based on user's row-level permissions"""

        # This would need to be implemented based on the specific ORM
        # For now, return the queryset as-is
        # In a real implementation, this would add WHERE clauses based on permissions

        return queryset
