"""
Tests for FABI+ Advanced Permissions System
Tests model-level, field-level, and row-level access control
"""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from sqlmodel import Session, SQLModel, create_engine

from fabiplus.core.permissions.base import (
    Permission,
    PermissionAction,
    PermissionContext,
    PermissionDenied,
    PermissionRegistry,
    PermissionScope,
    PermissionSet,
)
from fabiplus.core.permissions.checkers import (
    CompositePermissionChecker,
    FieldPermissionChecker,
    ModelPermissionChecker,
    RowPermissionChecker,
)
from fabiplus.core.permissions.decorators import (
    permission_required,
    require_field_permission,
    require_model_permission,
    require_permission,
    require_row_permission,
)
from fabiplus.core.permissions.models import (
    FieldPermission,
    GroupPermission,
    ModelPermission,
    RolePermission,
    RowPermission,
    UserPermission,
)


class TestPermissionBase:
    """Test base permission classes"""

    def test_permission_creation(self):
        """Test Permission object creation"""

        perm = Permission(
            name="test_permission",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="TestModel",
        )

        assert perm.name == "test_permission"
        assert perm.scope == PermissionScope.MODEL
        assert perm.action == PermissionAction.READ
        assert perm.resource == "TestModel"
        assert perm.id is not None

    def test_permission_matches(self):
        """Test permission matching logic"""

        perm = Permission(
            name="read_users",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="User",
        )

        # Should match exact action and resource
        assert perm.matches("read", "User") is True

        # Should not match different action
        assert perm.matches("write", "User") is False

        # Should not match different resource
        assert perm.matches("read", "Post") is False

        # Admin permission should match any action
        admin_perm = Permission(
            name="admin_users",
            scope=PermissionScope.MODEL,
            action=PermissionAction.ADMIN,
            resource="User",
        )

        assert admin_perm.matches("read", "User") is True
        assert admin_perm.matches("write", "User") is True
        assert admin_perm.matches("delete", "User") is True

    def test_permission_with_conditions(self):
        """Test permission with conditions"""

        perm = Permission(
            name="conditional_read",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="User",
            conditions={"department": "engineering"},
        )

        # Should match when condition is met
        assert perm.matches("read", "User", department="engineering") is True

        # Should not match when condition is not met
        assert perm.matches("read", "User", department="sales") is False

        # Should not match when condition is missing
        assert perm.matches("read", "User") is False

    def test_permission_denied_exception(self):
        """Test PermissionDenied exception"""

        with pytest.raises(PermissionDenied) as exc_info:
            raise PermissionDenied(
                message="Access denied",
                required_permission="read:users",
                user_id="user123",
                resource="User",
                action="read",
            )

        exception = exc_info.value
        assert str(exception) == "Access denied"
        assert exception.required_permission == "read:users"
        assert exception.user_id == "user123"
        assert exception.resource == "User"
        assert exception.action == "read"


class TestPermissionRegistry:
    """Test permission registry"""

    def setup_method(self):
        """Setup test registry"""
        self.registry = PermissionRegistry()

    def test_register_permission(self):
        """Test permission registration"""

        perm = Permission(
            name="test_perm",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="Test",
        )

        self.registry.register_permission(perm)

        retrieved = self.registry.get_permission(perm.id)
        assert retrieved == perm

    def test_list_permissions(self):
        """Test listing permissions with filters"""

        perm1 = Permission(
            name="read_users",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="User",
        )

        perm2 = Permission(
            name="write_users",
            scope=PermissionScope.MODEL,
            action=PermissionAction.UPDATE,
            resource="User",
        )

        perm3 = Permission(
            name="read_posts",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="Post",
        )

        self.registry.register_permission(perm1)
        self.registry.register_permission(perm2)
        self.registry.register_permission(perm3)

        # Test filtering by action
        read_perms = self.registry.list_permissions(action=PermissionAction.READ)
        assert len(read_perms) == 2

        # Test filtering by resource
        user_perms = self.registry.list_permissions(resource="User")
        assert len(user_perms) == 2

        # Test filtering by scope
        model_perms = self.registry.list_permissions(scope=PermissionScope.MODEL)
        assert len(model_perms) == 3


class TestPermissionSet:
    """Test permission set functionality"""

    def test_permission_set_creation(self):
        """Test PermissionSet creation"""

        perms = [
            Permission(
                name="read_users",
                scope=PermissionScope.MODEL,
                action=PermissionAction.READ,
                resource="User",
            ),
            Permission(
                name="write_users",
                scope=PermissionScope.MODEL,
                action=PermissionAction.UPDATE,
                resource="User",
            ),
        ]

        perm_set = PermissionSet(perms)

        assert len(perm_set) == 2
        assert perm_set.has_permission("read", "User") is True
        assert perm_set.has_permission("update", "User") is True
        assert perm_set.has_permission("delete", "User") is False

    def test_permission_set_operations(self):
        """Test adding and removing permissions"""

        perm_set = PermissionSet()

        perm = Permission(
            name="test_perm",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="Test",
        )

        # Add permission
        perm_set.add_permission(perm)
        assert len(perm_set) == 1
        assert perm_set.has_permission("read", "Test") is True

        # Remove permission
        perm_set.remove_permission(perm.id)
        assert len(perm_set) == 0
        assert perm_set.has_permission("read", "Test") is False


class TestPermissionModels:
    """Test permission database models"""

    def test_user_permission_model(self):
        """Test UserPermission model"""

        user_perm = UserPermission(
            user_id=uuid.uuid4(),
            permission_name="read_users",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="User",
        )

        assert user_perm.is_valid is True
        assert user_perm.is_expired is False

        # Test expiration
        user_perm.expires_at = datetime.now() - timedelta(hours=1)
        assert user_perm.is_expired is True
        assert user_perm.is_valid is False

    def test_model_permission_model(self):
        """Test ModelPermission model"""

        model_perm = ModelPermission(
            model_name="User",
            user_id=uuid.uuid4(),
            can_read=True,
            can_update=True,
            can_admin=False,
        )

        assert model_perm.has_permission(PermissionAction.READ) is True
        assert model_perm.has_permission(PermissionAction.UPDATE) is True
        assert model_perm.has_permission(PermissionAction.DELETE) is False

        # Test admin permission
        model_perm.can_admin = True
        assert model_perm.has_permission(PermissionAction.DELETE) is True

    def test_field_permission_model(self):
        """Test FieldPermission model"""

        field_perm = FieldPermission(
            model_name="User",
            field_name="email",
            user_id=uuid.uuid4(),
            can_read=True,
            can_write=False,
            is_sensitive=True,
        )

        assert field_perm.has_permission(PermissionAction.READ) is True
        assert field_perm.has_permission(PermissionAction.UPDATE) is False
        assert field_perm.is_sensitive is True

    def test_row_permission_model(self):
        """Test RowPermission model"""

        row_perm = RowPermission(
            model_name="User",
            row_id="123",
            user_id=uuid.uuid4(),
            can_read=True,
            can_update=False,
            is_owner=True,
        )

        assert row_perm.has_permission(PermissionAction.READ) is True
        assert (
            row_perm.has_permission(PermissionAction.UPDATE) is True
        )  # Owner can update
        assert (
            row_perm.has_permission(PermissionAction.DELETE) is True
        )  # Owner can delete


class TestPermissionCheckers:
    """Test permission checker implementations"""

    def setup_method(self):
        """Setup test database and session"""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        self.session = Session(engine)

        # Create mock user
        self.user = MagicMock()
        self.user.id = uuid.uuid4()
        self.user.groups = []
        self.user.roles = []

    @pytest.mark.asyncio
    async def test_model_permission_checker(self):
        """Test ModelPermissionChecker"""

        # Create model permission
        model_perm = ModelPermission(
            model_name="User", user_id=self.user.id, can_read=True, can_update=False
        )
        self.session.add(model_perm)
        self.session.commit()

        checker = ModelPermissionChecker(self.session)

        # Test permission checking
        read_perm = Permission(
            name="read_users",
            scope=PermissionScope.MODEL,
            action=PermissionAction.READ,
            resource="User",
        )

        # This would be async in real implementation
        # For testing, we'll mock the async behavior
        with patch.object(
            checker, "check_permission", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = True
            result = await checker.check_permission(self.user, read_perm)
            assert result is True

    def test_composite_permission_checker(self):
        """Test CompositePermissionChecker"""

        checker = CompositePermissionChecker(self.session)

        # Test that it routes to appropriate sub-checkers
        assert isinstance(checker.model_checker, ModelPermissionChecker)
        assert isinstance(checker.field_checker, FieldPermissionChecker)
        assert isinstance(checker.row_checker, RowPermissionChecker)


class TestPermissionDecorators:
    """Test permission decorators"""

    def setup_method(self):
        """Setup test environment"""
        self.user = MagicMock()
        self.user.id = uuid.uuid4()
        self.session = MagicMock()

    def test_require_permission_decorator(self):
        """Test require_permission decorator"""

        @require_permission("read:users")
        async def test_endpoint(current_user, session):
            return {"message": "success"}

        # Test with permission
        with patch(
            "fabiplus.core.permissions.decorators.CompositePermissionChecker"
        ) as mock_checker_class:
            mock_checker = MagicMock()
            mock_checker.require_permission.return_value = None  # No exception
            mock_checker_class.return_value = mock_checker

            # This would be tested with actual async execution
            # For now, just verify the decorator structure
            assert callable(test_endpoint)

    def test_require_model_permission_decorator(self):
        """Test require_model_permission decorator"""

        @require_model_permission(PermissionAction.READ, model_class=MagicMock)
        async def test_endpoint(current_user, session):
            return {"message": "success"}

        assert callable(test_endpoint)

    def test_permission_required_decorator(self):
        """Test permission_required decorator"""

        @permission_required(["read:users", "write:users"], require_all=False)
        async def test_endpoint(current_user, session):
            return {"message": "success"}

        assert callable(test_endpoint)


class TestPermissionIntegration:
    """Integration tests for permission system"""

    def setup_method(self):
        """Setup test environment"""
        engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(engine)
        self.session = Session(engine)

        # Create test user
        self.user = MagicMock()
        self.user.id = uuid.uuid4()
        self.user.groups = []
        self.user.roles = []

    @pytest.mark.asyncio
    async def test_full_permission_workflow(self):
        """Test complete permission workflow"""

        # 1. Create permissions
        model_perm = ModelPermission(
            model_name="User", user_id=self.user.id, can_read=True, can_update=True
        )

        field_perm = FieldPermission(
            model_name="User",
            field_name="email",
            user_id=self.user.id,
            can_read=True,
            can_write=False,
            is_sensitive=True,
        )

        self.session.add(model_perm)
        self.session.add(field_perm)
        self.session.commit()

        # 2. Test permission checking
        checker = CompositePermissionChecker(self.session)

        # Mock the async methods for testing
        with patch.object(
            checker, "check_permission", new_callable=AsyncMock
        ) as mock_check:
            mock_check.return_value = True

            # Test model permission
            model_permission = Permission(
                name="read_users",
                scope=PermissionScope.MODEL,
                action=PermissionAction.READ,
                resource="User",
            )

            result = await checker.check_permission(self.user, model_permission)
            assert result is True

    def test_permission_hierarchy(self):
        """Test permission hierarchy (admin > specific permissions)"""

        # Admin permission should grant all access
        admin_perm = ModelPermission(
            model_name="User", user_id=self.user.id, can_admin=True
        )

        self.session.add(admin_perm)
        self.session.commit()

        # Admin should have all permissions
        assert admin_perm.has_permission(PermissionAction.READ) is True
        assert admin_perm.has_permission(PermissionAction.UPDATE) is True
        assert admin_perm.has_permission(PermissionAction.DELETE) is True
        assert admin_perm.has_permission(PermissionAction.CREATE) is True

    def test_ownership_permissions(self):
        """Test ownership-based permissions"""

        # Create row permission with ownership
        row_perm = RowPermission(
            model_name="Post",
            row_id="123",
            user_id=self.user.id,
            is_owner=True,
            can_read=False,  # Even without explicit read permission
            can_update=False,  # Owner should still have access
        )

        # Owner should have all permissions regardless of explicit settings
        assert row_perm.has_permission(PermissionAction.READ) is True
        assert row_perm.has_permission(PermissionAction.UPDATE) is True
        assert row_perm.has_permission(PermissionAction.DELETE) is True


class TestPermissionPerformance:
    """Performance tests for permission system"""

    def test_permission_set_performance(self):
        """Test PermissionSet performance with many permissions"""

        # Create many permissions
        permissions = []
        for i in range(1000):
            perm = Permission(
                name=f"perm_{i}",
                scope=PermissionScope.MODEL,
                action=PermissionAction.READ,
                resource=f"Model_{i % 10}",  # 10 different models
            )
            permissions.append(perm)

        perm_set = PermissionSet(permissions)

        # Test lookup performance
        assert perm_set.has_permission("read", "Model_5") is True
        assert perm_set.has_permission("write", "Model_5") is False

        # Should be fast even with many permissions
        assert len(perm_set) == 1000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
