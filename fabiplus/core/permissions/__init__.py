"""
Advanced permissions system for FABI+ framework
Provides model-level, field-level, and row-level access control
"""

from .base import Permission, PermissionChecker, PermissionDenied, PermissionRegistry
from .decorators import (
    check_permissions,
    permission_required,
    require_field_permission,
    require_model_permission,
    require_permission,
    require_row_permission,
)
from .models import (
    FieldPermission,
    GroupPermission,
    ModelPermission,
    RolePermission,
    RowPermission,
    UserPermission,
)

# from .middleware import (
#     PermissionMiddleware,
#     ModelPermissionMiddleware,
#     APIPermissionMiddleware
# )

# from .checkers import (
#     ModelPermissionChecker,
#     FieldPermissionChecker,
#     RowPermissionChecker,
#     CompositePermissionChecker
# )

# from .policies import (
#     PermissionPolicy,
#     ModelPolicy,
#     FieldPolicy,
#     RowPolicy,
#     DefaultPolicy
# )

# from .utils import (
#     get_user_permissions,
#     check_user_permission,
#     get_model_permissions,
#     get_field_permissions,
#     get_row_permissions,
#     merge_permissions
# )

__all__ = [
    # Base classes
    "Permission",
    "PermissionChecker",
    "PermissionDenied",
    "PermissionRegistry",
    # Models
    "ModelPermission",
    "FieldPermission",
    "RowPermission",
    "UserPermission",
    "GroupPermission",
    "RolePermission",
    # Decorators
    "require_permission",
    "require_model_permission",
    "require_field_permission",
    "require_row_permission",
    "permission_required",
    "check_permissions",
    # Middleware
    "PermissionMiddleware",
    "ModelPermissionMiddleware",
    "APIPermissionMiddleware",
    # Checkers
    "ModelPermissionChecker",
    "FieldPermissionChecker",
    "RowPermissionChecker",
    "CompositePermissionChecker",
    # Policies
    "PermissionPolicy",
    "ModelPolicy",
    "FieldPolicy",
    "RowPolicy",
    "DefaultPolicy",
    # Utilities
    "get_user_permissions",
    "check_user_permission",
    "get_model_permissions",
    "get_field_permissions",
    "get_row_permissions",
    "merge_permissions",
]
