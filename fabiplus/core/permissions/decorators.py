"""
Permission decorators for FABI+ framework
"""

import functools
from inspect import signature
from typing import Any, Callable, List, Optional, Union

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

from .base import Permission, PermissionAction, PermissionDenied, PermissionScope
from .checkers import CompositePermissionChecker

security = HTTPBearer()


def require_permission(
    permission: Union[str, Permission],
    resource_param: Optional[str] = None,
    user_param: str = "current_user",
    session_param: str = "session",
):
    """
    Decorator to require specific permission for endpoint access

    Args:
        permission: Permission string or Permission object
        resource_param: Parameter name that contains the resource
        user_param: Parameter name that contains the current user
        session_param: Parameter name that contains the database session
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Get user and session from function parameters
            user = kwargs.get(user_param)
            session = kwargs.get(session_param)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available",
                )

            # Get resource if specified
            resource = None
            if resource_param and resource_param in kwargs:
                resource = kwargs[resource_param]

            # Check permission
            checker = CompositePermissionChecker(session)

            try:
                await checker.require_permission(user, permission, resource)
            except PermissionDenied as e:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_model_permission(
    action: PermissionAction,
    model_param: Optional[str] = None,
    model_class: Optional[type] = None,
    user_param: str = "current_user",
    session_param: str = "session",
):
    """
    Decorator to require model-level permission

    Args:
        action: Permission action required
        model_param: Parameter name that contains the model instance
        model_class: Model class (if not using model_param)
        user_param: Parameter name that contains the current user
        session_param: Parameter name that contains the database session
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get(user_param)
            session = kwargs.get(session_param)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available",
                )

            # Determine model
            model = None
            if model_param and model_param in kwargs:
                model = kwargs[model_param]
                model_name = model.__class__.__name__
            elif model_class:
                model_name = model_class.__name__
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Model not specified for permission check",
                )

            # Create permission
            permission = Permission(
                name=f"model:{action}:{model_name}",
                scope=PermissionScope.MODEL,
                action=action,
                resource=model_name,
            )

            # Check permission
            checker = CompositePermissionChecker(session)

            try:
                await checker.require_permission(user, permission, model)
            except PermissionDenied as e:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_field_permission(
    action: PermissionAction,
    field_name: str,
    model_param: Optional[str] = None,
    model_class: Optional[type] = None,
    user_param: str = "current_user",
    session_param: str = "session",
):
    """
    Decorator to require field-level permission

    Args:
        action: Permission action required
        field_name: Name of the field
        model_param: Parameter name that contains the model instance
        model_class: Model class (if not using model_param)
        user_param: Parameter name that contains the current user
        session_param: Parameter name that contains the database session
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get(user_param)
            session = kwargs.get(session_param)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available",
                )

            # Determine model
            model = None
            if model_param and model_param in kwargs:
                model = kwargs[model_param]
                model_name = model.__class__.__name__
            elif model_class:
                model_name = model_class.__name__
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Model not specified for permission check",
                )

            # Create permission
            permission = Permission(
                name=f"field:{action}:{model_name}.{field_name}",
                scope=PermissionScope.FIELD,
                action=action,
                resource=f"{model_name}.{field_name}",
            )

            # Check permission
            checker = CompositePermissionChecker(session)

            try:
                await checker.require_permission(
                    user, permission, model, field_name=field_name
                )
            except PermissionDenied as e:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def require_row_permission(
    action: PermissionAction,
    instance_param: str,
    user_param: str = "current_user",
    session_param: str = "session",
):
    """
    Decorator to require row-level permission

    Args:
        action: Permission action required
        instance_param: Parameter name that contains the model instance
        user_param: Parameter name that contains the current user
        session_param: Parameter name that contains the database session
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get(user_param)
            session = kwargs.get(session_param)
            instance = kwargs.get(instance_param)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available",
                )

            if not instance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
                )

            # Create permission
            model_name = instance.__class__.__name__
            permission = Permission(
                name=f"row:{action}:{model_name}",
                scope=PermissionScope.ROW,
                action=action,
                resource=model_name,
            )

            # Check permission
            checker = CompositePermissionChecker(session)

            try:
                await checker.require_permission(user, permission, instance)
            except PermissionDenied as e:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail=str(e)
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def permission_required(
    permissions: Union[str, List[str], Permission, List[Permission]],
    require_all: bool = True,
    user_param: str = "current_user",
    session_param: str = "session",
):
    """
    Decorator to require multiple permissions

    Args:
        permissions: Single permission or list of permissions
        require_all: If True, require all permissions; if False, require any
        user_param: Parameter name that contains the current user
        session_param: Parameter name that contains the database session
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get(user_param)
            session = kwargs.get(session_param)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not session:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Database session not available",
                )

            # Normalize permissions to list
            if not isinstance(permissions, list):
                perm_list = [permissions]
            else:
                perm_list = permissions

            # Check permissions
            checker = CompositePermissionChecker(session)
            results = []

            for perm in perm_list:
                try:
                    has_perm = await checker.check_permission(user, perm)
                    results.append(has_perm)
                except Exception:
                    results.append(False)

            # Evaluate results
            if require_all:
                has_access = all(results)
            else:
                has_access = any(results)

            if not has_access:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient permissions",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def check_permissions(user_param: str = "current_user", session_param: str = "session"):
    """
    Decorator that adds permission checking capability to endpoint
    Adds a 'check_permission' function to kwargs

    Args:
        user_param: Parameter name that contains the current user
        session_param: Parameter name that contains the database session
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get(user_param)
            session = kwargs.get(session_param)

            if user and session:
                checker = CompositePermissionChecker(session)

                async def check_permission(
                    permission: Union[str, Permission],
                    resource: Optional[Any] = None,
                    **check_kwargs,
                ) -> bool:
                    return await checker.check_permission(
                        user, permission, resource, **check_kwargs
                    )

                kwargs["check_permission"] = check_permission

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def owner_required(
    instance_param: str, owner_field: str = "owner_id", user_param: str = "current_user"
):
    """
    Decorator to require ownership of a resource

    Args:
        instance_param: Parameter name that contains the model instance
        owner_field: Field name that contains the owner ID
        user_param: Parameter name that contains the current user
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            user = kwargs.get(user_param)
            instance = kwargs.get(instance_param)

            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                )

            if not instance:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found"
                )

            # Check ownership
            owner_id = getattr(instance, owner_field, None)
            if owner_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied: You don't own this resource",
                )

            return await func(*args, **kwargs)

        return wrapper

    return decorator
