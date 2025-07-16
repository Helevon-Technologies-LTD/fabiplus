"""
Base permission classes and interfaces for FABI+ permissions system
"""

import uuid
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Type, Union

from pydantic import BaseModel


class PermissionAction(str, Enum):
    """Standard permission actions"""

    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    LIST = "list"
    EXECUTE = "execute"
    ADMIN = "admin"


class PermissionLevel(str, Enum):
    """Permission levels"""

    NONE = "none"
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


class PermissionScope(str, Enum):
    """Permission scopes"""

    GLOBAL = "global"
    MODEL = "model"
    FIELD = "field"
    ROW = "row"
    CUSTOM = "custom"


class PermissionDenied(Exception):
    """Exception raised when permission is denied"""

    def __init__(
        self,
        message: str = "Permission denied",
        required_permission: Optional[str] = None,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
    ):
        self.message = message
        self.required_permission = required_permission
        self.user_id = user_id
        self.resource = resource
        self.action = action
        super().__init__(self.message)


class Permission(BaseModel):
    """Base permission class"""

    id: str = None
    name: str
    description: str = ""
    scope: PermissionScope
    action: PermissionAction
    resource: Optional[str] = None
    conditions: Dict[str, Any] = {}
    metadata: Dict[str, Any] = {}

    def __init__(self, **data):
        if "id" not in data or data["id"] is None:
            data["id"] = str(uuid.uuid4())
        super().__init__(**data)

    def matches(self, action: str, resource: str = None, **kwargs) -> bool:
        """Check if this permission matches the given action and resource"""

        # Check action
        if self.action != action and self.action != PermissionAction.ADMIN:
            return False

        # Check resource
        if self.resource and resource and self.resource != resource:
            return False

        # Check conditions
        for condition_key, condition_value in self.conditions.items():
            if condition_key in kwargs:
                if kwargs[condition_key] != condition_value:
                    return False

        return True

    def __str__(self):
        return f"{self.scope}:{self.action}:{self.resource or '*'}"


class PermissionChecker(ABC):
    """Abstract base class for permission checkers"""

    @abstractmethod
    async def check_permission(
        self,
        user: Any,
        permission: Union[str, Permission],
        resource: Optional[Any] = None,
        **kwargs,
    ) -> bool:
        """Check if user has the specified permission"""
        pass

    @abstractmethod
    async def get_user_permissions(
        self,
        user: Any,
        scope: Optional[PermissionScope] = None,
        resource: Optional[str] = None,
    ) -> List[Permission]:
        """Get all permissions for a user"""
        pass

    async def require_permission(
        self,
        user: Any,
        permission: Union[str, Permission],
        resource: Optional[Any] = None,
        **kwargs,
    ) -> None:
        """Require permission or raise PermissionDenied"""

        has_permission = await self.check_permission(
            user, permission, resource, **kwargs
        )

        if not has_permission:
            raise PermissionDenied(
                message=f"Permission denied: {permission}",
                required_permission=str(permission),
                user_id=getattr(user, "id", None),
                resource=str(resource) if resource else None,
            )


class PermissionRegistry:
    """Registry for managing permissions and permission checkers"""

    def __init__(self):
        self._permissions: Dict[str, Permission] = {}
        self._checkers: Dict[PermissionScope, PermissionChecker] = {}
        self._policies: Dict[str, Any] = {}

    def register_permission(self, permission: Permission) -> None:
        """Register a permission"""
        self._permissions[permission.id] = permission

    def register_checker(
        self, scope: PermissionScope, checker: PermissionChecker
    ) -> None:
        """Register a permission checker for a scope"""
        self._checkers[scope] = checker

    def register_policy(self, name: str, policy: Any) -> None:
        """Register a permission policy"""
        self._policies[name] = policy

    def get_permission(self, permission_id: str) -> Optional[Permission]:
        """Get permission by ID"""
        return self._permissions.get(permission_id)

    def get_checker(self, scope: PermissionScope) -> Optional[PermissionChecker]:
        """Get permission checker for scope"""
        return self._checkers.get(scope)

    def get_policy(self, name: str) -> Optional[Any]:
        """Get permission policy by name"""
        return self._policies.get(name)

    def list_permissions(
        self,
        scope: Optional[PermissionScope] = None,
        action: Optional[PermissionAction] = None,
        resource: Optional[str] = None,
    ) -> List[Permission]:
        """List permissions with optional filtering"""

        permissions = list(self._permissions.values())

        if scope:
            permissions = [p for p in permissions if p.scope == scope]

        if action:
            permissions = [p for p in permissions if p.action == action]

        if resource:
            permissions = [p for p in permissions if p.resource == resource]

        return permissions

    async def check_permission(
        self,
        user: Any,
        permission: Union[str, Permission],
        resource: Optional[Any] = None,
        **kwargs,
    ) -> bool:
        """Check permission using appropriate checker"""

        if isinstance(permission, str):
            # Try to find permission by ID or name
            perm_obj = self.get_permission(permission)
            if not perm_obj:
                # Create temporary permission from string
                parts = permission.split(":")
                if len(parts) >= 2:
                    scope = PermissionScope(parts[0])
                    action = PermissionAction(parts[1])
                    resource_name = parts[2] if len(parts) > 2 else None
                    perm_obj = Permission(
                        name=permission,
                        scope=scope,
                        action=action,
                        resource=resource_name,
                    )
                else:
                    return False
        else:
            perm_obj = permission

        # Get appropriate checker
        checker = self.get_checker(perm_obj.scope)
        if not checker:
            return False

        return await checker.check_permission(user, perm_obj, resource, **kwargs)


# Global permission registry
permission_registry = PermissionRegistry()


class PermissionContext:
    """Context for permission checking"""

    def __init__(
        self,
        user: Any,
        resource: Optional[Any] = None,
        action: Optional[str] = None,
        extra_context: Optional[Dict[str, Any]] = None,
    ):
        self.user = user
        self.resource = resource
        self.action = action
        self.extra_context = extra_context or {}

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context"""
        if hasattr(self, key):
            return getattr(self, key)
        return self.extra_context.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set value in context"""
        self.extra_context[key] = value


class PermissionRule(BaseModel):
    """Rule for permission evaluation"""

    name: str
    condition: str  # Python expression
    description: str = ""
    priority: int = 0

    def evaluate(self, context: PermissionContext) -> bool:
        """Evaluate rule against context"""
        try:
            # Create safe evaluation environment
            safe_globals = {
                "__builtins__": {},
                "user": context.user,
                "resource": context.resource,
                "action": context.action,
                "context": context,
                "hasattr": hasattr,
                "getattr": getattr,
                "isinstance": isinstance,
                "str": str,
                "int": int,
                "bool": bool,
                "list": list,
                "dict": dict,
            }

            # Add extra context variables
            safe_globals.update(context.extra_context)

            # Evaluate condition
            result = eval(self.condition, safe_globals, {})
            return bool(result)

        except Exception:
            # If evaluation fails, deny permission
            return False


class ConditionalPermission(Permission):
    """Permission with conditional rules"""

    rules: List[PermissionRule] = []
    require_all_rules: bool = True  # AND vs OR logic

    def check_conditions(self, context: PermissionContext) -> bool:
        """Check if all conditions are met"""

        if not self.rules:
            return True

        results = []
        for rule in sorted(self.rules, key=lambda r: r.priority, reverse=True):
            result = rule.evaluate(context)
            results.append(result)

        if self.require_all_rules:
            return all(results)
        else:
            return any(results)


class PermissionSet:
    """Set of permissions for efficient checking"""

    def __init__(self, permissions: List[Permission] = None):
        self.permissions = permissions or []
        self._permission_map = {p.id: p for p in self.permissions}
        self._action_map = {}
        self._resource_map = {}

        # Build lookup maps
        for perm in self.permissions:
            # Action map
            if perm.action not in self._action_map:
                self._action_map[perm.action] = []
            self._action_map[perm.action].append(perm)

            # Resource map
            if perm.resource:
                if perm.resource not in self._resource_map:
                    self._resource_map[perm.resource] = []
                self._resource_map[perm.resource].append(perm)

    def has_permission(self, action: str, resource: str = None, **kwargs) -> bool:
        """Check if permission set contains matching permission"""

        # Check action-based permissions
        action_perms = self._action_map.get(action, [])
        admin_perms = self._action_map.get(PermissionAction.ADMIN, [])

        all_perms = action_perms + admin_perms

        for perm in all_perms:
            if perm.matches(action, resource, **kwargs):
                return True

        return False

    def add_permission(self, permission: Permission) -> None:
        """Add permission to set"""
        if permission.id not in self._permission_map:
            self.permissions.append(permission)
            self._permission_map[permission.id] = permission

            # Update lookup maps
            if permission.action not in self._action_map:
                self._action_map[permission.action] = []
            self._action_map[permission.action].append(permission)

            if permission.resource:
                if permission.resource not in self._resource_map:
                    self._resource_map[permission.resource] = []
                self._resource_map[permission.resource].append(permission)

    def remove_permission(self, permission_id: str) -> None:
        """Remove permission from set"""
        if permission_id in self._permission_map:
            perm = self._permission_map[permission_id]
            self.permissions.remove(perm)
            del self._permission_map[permission_id]

            # Update lookup maps
            if perm.action in self._action_map:
                self._action_map[perm.action].remove(perm)

            if perm.resource and perm.resource in self._resource_map:
                self._resource_map[perm.resource].remove(perm)

    def __len__(self):
        return len(self.permissions)

    def __iter__(self):
        return iter(self.permissions)
