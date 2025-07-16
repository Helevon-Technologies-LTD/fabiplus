"""
Database models for permissions system
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlmodel import Field, Relationship, SQLModel

from .base import PermissionAction, PermissionLevel, PermissionScope

# from pydantic import validator  # Not used currently


class UserPermission(SQLModel, table=True):
    """Direct user permissions"""

    __tablename__ = "user_permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="users.id", description="User ID")
    permission_name: str = Field(max_length=100, description="Permission name")
    scope: PermissionScope = Field(description="Permission scope")
    action: PermissionAction = Field(description="Permission action")
    resource: Optional[str] = Field(
        default=None, max_length=100, description="Resource identifier"
    )
    resource_id: Optional[str] = Field(
        default=None, max_length=100, description="Specific resource ID"
    )

    # Conditions and metadata
    conditions: Optional[str] = Field(
        default="{}", description="JSON string of permission conditions"
    )
    extra_data: Optional[str] = Field(
        default="{}", description="JSON string of additional metadata"
    )

    # Timestamps
    granted_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = Field(
        default=None, description="Permission expiration"
    )
    granted_by: Optional[uuid.UUID] = Field(
        default=None, description="Who granted this permission"
    )

    # Status
    is_active: bool = Field(default=True, description="Whether permission is active")

    class Config:
        _verbose_name = "User Permission"
        _verbose_name_plural = "User Permissions"

    def __str__(self):
        return f"{self.user_id}: {self.scope}:{self.action}:{self.resource or '*'}"

    @property
    def is_expired(self) -> bool:
        """Check if permission is expired"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if permission is valid (active and not expired)"""
        return self.is_active and not self.is_expired


class GroupPermission(SQLModel, table=True):
    """Group-based permissions"""

    __tablename__ = "group_permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # group_id removed - using role-based permissions instead
    permission_name: str = Field(max_length=100, description="Permission name")
    scope: PermissionScope = Field(description="Permission scope")
    action: PermissionAction = Field(description="Permission action")
    resource: Optional[str] = Field(
        default=None, max_length=100, description="Resource identifier"
    )

    # Conditions and metadata
    conditions: Optional[str] = Field(
        default="{}", description="JSON string of permission conditions"
    )
    extra_data: Optional[str] = Field(
        default="{}", description="JSON string of additional metadata"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[uuid.UUID] = Field(
        default=None, description="Who created this permission"
    )

    # Status
    is_active: bool = Field(default=True, description="Whether permission is active")

    class Config:
        _verbose_name = "Group Permission"
        _verbose_name_plural = "Group Permissions"

    def __str__(self):
        return f"Group Permission: {self.scope}:{self.action}:{self.resource or '*'}"


class Role(SQLModel, table=True):
    """Role model for grouping permissions"""

    __tablename__ = "roles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, unique=True, description="Role name")
    description: Optional[str] = Field(
        default="", max_length=500, description="Role description"
    )
    is_active: bool = Field(default=True, description="Whether role is active")
    is_system: bool = Field(default=False, description="System roles cannot be deleted")

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[uuid.UUID] = Field(
        default=None, description="Who created this role"
    )

    class Config:
        _verbose_name = "Role"
        _verbose_name_plural = "Roles"

    def __str__(self):
        return self.name


class RolePermission(SQLModel, table=True):
    """Role-based permissions"""

    __tablename__ = "role_permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    role_id: uuid.UUID = Field(foreign_key="roles.id", description="Role ID")
    permission_name: str = Field(max_length=100, description="Permission name")
    scope: PermissionScope = Field(description="Permission scope")
    action: PermissionAction = Field(description="Permission action")
    resource: Optional[str] = Field(
        default=None, max_length=100, description="Resource identifier"
    )

    # Conditions and metadata
    conditions: Optional[str] = Field(
        default="{}", description="JSON string of permission conditions"
    )
    extra_data: Optional[str] = Field(
        default="{}", description="JSON string of additional metadata"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Status
    is_active: bool = Field(default=True, description="Whether permission is active")

    class Config:
        _verbose_name = "Role Permission"
        _verbose_name_plural = "Role Permissions"

    def __str__(self):
        return f"Role {self.role_id}: {self.scope}:{self.action}:{self.resource or '*'}"


class ModelPermission(SQLModel, table=True):
    """Model-level permissions"""

    __tablename__ = "model_permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_name: str = Field(max_length=100, description="Model class name")
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    # group_id removed - using role-based permissions instead
    role_id: Optional[uuid.UUID] = Field(default=None, foreign_key="roles.id")

    # Permissions
    can_create: bool = Field(default=False, description="Can create new instances")
    can_read: bool = Field(default=False, description="Can read instances")
    can_update: bool = Field(default=False, description="Can update instances")
    can_delete: bool = Field(default=False, description="Can delete instances")
    can_list: bool = Field(default=False, description="Can list instances")
    can_admin: bool = Field(default=False, description="Full admin access")

    # Conditions
    conditions: Optional[str] = Field(
        default="{}", description="JSON string of additional conditions"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        _verbose_name = "Model Permission"
        _verbose_name_plural = "Model Permissions"

    def __str__(self):
        subject = f"User {self.user_id}" if self.user_id else f"Role {self.role_id}"
        return f"{subject}: {self.model_name}"

    def has_permission(self, action: PermissionAction) -> bool:
        """Check if this permission allows the given action"""
        if self.can_admin:
            return True

        action_map = {
            PermissionAction.CREATE: self.can_create,
            PermissionAction.READ: self.can_read,
            PermissionAction.UPDATE: self.can_update,
            PermissionAction.DELETE: self.can_delete,
            PermissionAction.LIST: self.can_list,
        }

        return action_map.get(action, False)


class FieldPermission(SQLModel, table=True):
    """Field-level permissions"""

    __tablename__ = "field_permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_name: str = Field(max_length=100, description="Model class name")
    field_name: str = Field(max_length=100, description="Field name")
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    # group_id removed - using role-based permissions instead
    role_id: Optional[uuid.UUID] = Field(default=None, foreign_key="roles.id")

    # Permissions
    can_read: bool = Field(default=False, description="Can read field value")
    can_write: bool = Field(default=False, description="Can write field value")
    can_admin: bool = Field(default=False, description="Full field admin access")

    # Field-specific settings
    is_sensitive: bool = Field(
        default=False, description="Field contains sensitive data"
    )
    mask_value: bool = Field(
        default=False, description="Mask field value when displayed"
    )
    default_value: Optional[str] = Field(
        default=None, description="Default value for restricted access"
    )

    # Conditions
    conditions: Optional[str] = Field(
        default="{}", description="JSON string of additional conditions"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        _verbose_name = "Field Permission"
        _verbose_name_plural = "Field Permissions"

    def __str__(self):
        subject = f"User {self.user_id}" if self.user_id else f"Role {self.role_id}"
        return f"{subject}: {self.model_name}.{self.field_name}"

    def has_permission(self, action: PermissionAction) -> bool:
        """Check if this permission allows the given action"""
        if self.can_admin:
            return True

        if action in [PermissionAction.READ, PermissionAction.LIST]:
            return self.can_read
        elif action in [PermissionAction.CREATE, PermissionAction.UPDATE]:
            return self.can_write

        return False


class RowPermission(SQLModel, table=True):
    """Row-level permissions"""

    __tablename__ = "row_permissions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    model_name: str = Field(max_length=100, description="Model class name")
    row_id: str = Field(max_length=100, description="Specific row/instance ID")
    user_id: Optional[uuid.UUID] = Field(default=None, foreign_key="users.id")
    # group_id removed - using role-based permissions instead
    role_id: Optional[uuid.UUID] = Field(default=None, foreign_key="roles.id")

    # Permissions
    can_read: bool = Field(default=False, description="Can read this row")
    can_update: bool = Field(default=False, description="Can update this row")
    can_delete: bool = Field(default=False, description="Can delete this row")
    can_admin: bool = Field(default=False, description="Full row admin access")

    # Ownership
    is_owner: bool = Field(default=False, description="User is owner of this row")
    owner_field: Optional[str] = Field(
        default=None, description="Field that determines ownership"
    )

    # Conditions
    conditions: Optional[str] = Field(
        default="{}", description="JSON string of additional conditions"
    )

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    expires_at: Optional[datetime] = Field(
        default=None, description="Permission expiration"
    )

    class Config:
        _verbose_name = "Row Permission"
        _verbose_name_plural = "Row Permissions"

    def __str__(self):
        subject = f"User {self.user_id}" if self.user_id else f"Role {self.role_id}"
        return f"{subject}: {self.model_name}#{self.row_id}"

    def has_permission(self, action: PermissionAction) -> bool:
        """Check if this permission allows the given action"""
        if self.can_admin or self.is_owner:
            return True

        action_map = {
            PermissionAction.READ: self.can_read,
            PermissionAction.UPDATE: self.can_update,
            PermissionAction.DELETE: self.can_delete,
        }

        return action_map.get(action, False)

    @property
    def is_expired(self) -> bool:
        """Check if permission is expired"""
        if not self.expires_at:
            return False
        return datetime.now() > self.expires_at

    @property
    def is_valid(self) -> bool:
        """Check if permission is valid (not expired)"""
        return not self.is_expired


class PermissionTemplate(SQLModel, table=True):
    """Templates for common permission patterns"""

    __tablename__ = "permission_templates"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(max_length=100, unique=True, description="Template name")
    description: str = Field(default="", description="Template description")

    # Template configuration
    permissions: Optional[str] = Field(
        default="{}", description="JSON string of permission configuration"
    )
    applies_to: Optional[str] = Field(
        default="[]", description="JSON string of models this template applies to"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    created_by: Optional[uuid.UUID] = Field(
        default=None, description="Template creator"
    )

    # Status
    is_active: bool = Field(default=True, description="Whether template is active")
    is_system: bool = Field(default=False, description="System-defined template")

    class Config:
        _verbose_name = "Permission Template"
        _verbose_name_plural = "Permission Templates"

    def __str__(self):
        return self.name


class PermissionAuditLog(SQLModel, table=True):
    """Audit log for permission changes"""

    __tablename__ = "permission_audit_logs"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    # What happened
    action: str = Field(max_length=50, description="Action performed")
    permission_type: str = Field(max_length=50, description="Type of permission")
    permission_id: Optional[uuid.UUID] = Field(
        default=None, description="Permission ID"
    )

    # Who did it
    user_id: Optional[uuid.UUID] = Field(
        default=None, description="User who performed action"
    )
    admin_user_id: Optional[uuid.UUID] = Field(
        default=None, description="Admin who made the change"
    )

    # When and where
    timestamp: datetime = Field(default_factory=datetime.now)
    ip_address: Optional[str] = Field(
        default=None, max_length=45, description="IP address"
    )
    user_agent: Optional[str] = Field(default=None, description="User agent")

    # Details
    old_values: Optional[str] = Field(
        default=None, description="JSON string of previous values"
    )
    new_values: Optional[str] = Field(
        default=None, description="JSON string of new values"
    )
    extra_data: Optional[str] = Field(
        default="{}", description="JSON string of additional metadata"
    )

    class Config:
        _verbose_name = "Permission Audit Log"
        _verbose_name_plural = "Permission Audit Logs"

    def __str__(self):
        return f"{self.action} - {self.permission_type} - {self.timestamp}"


# Register all permission models
from ..models import ModelRegistry

ModelRegistry.register(Role)
ModelRegistry.register(UserPermission)
ModelRegistry.register(GroupPermission)
ModelRegistry.register(RolePermission)
ModelRegistry.register(ModelPermission)
ModelRegistry.register(FieldPermission)
ModelRegistry.register(RowPermission)
ModelRegistry.register(PermissionTemplate)
ModelRegistry.register(PermissionAuditLog)
