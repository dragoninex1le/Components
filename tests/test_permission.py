"""Tests for Permission model and repository."""

import pytest
from moto import mock_dynamodb, mock_events
from boto3 import resource, client

from porth_common.models.permission import Permission
from porth_common.repositories.permission_repo import PermissionRepository


@pytest.fixture
def permission_repo(dynamodb, dynamodb_tables, events_client):
    """Create a PermissionRepository with mocked DynamoDB and EventBridge."""
    return PermissionRepository(
        dynamodb_resource=dynamodb,
        events_client=events_client,
    )


class TestPermissionModel:
    """Test Permission Pydantic model."""

    def test_permission_creation(self):
        """Test creating a Permission instance."""
        perm = Permission(
            id="perm-1",
            key="users.read",
            display_name="Read Users",
            app_namespace="cart-agent",
            tenant_id="tenant-1",
            category="Users",
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert perm.id == "perm-1"
        assert perm.key == "users.read"
        assert perm.category == "Users"

    def test_permission_with_optional_fields(self):
        """Test creating a Permission with optional fields."""
        perm = Permission(
            id="perm-2",
            key="orders.write",
            display_name="Write Orders",
            description="Create and update orders",
            app_namespace="cart-agent",
            tenant_id="tenant-1",
            category="Orders",
            icon_hint="edit",
            sort_order=5,
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert perm.description == "Create and update orders"
        assert perm.icon_hint == "edit"
        assert perm.sort_order == 5


class TestPermissionRepository:
    """Test PermissionRepository CRUD operations."""

    def test_create_permission(self, permission_repo):
        """Test creating a permission."""
        perm = permission_repo.create(
            tenant_id="tenant-1",
            app_namespace="cart-agent",
            name="users.read",
            description="Read user data",
            category="Users",
        )
        assert perm.id is not None
        assert perm.name == "users.read"
        assert perm.category == "Users"

    def test_get_permission_by_id(self, permission_repo):
        """Test retrieving a permission by ID."""
        created_perm = permission_repo.create(
            tenant_id="tenant-1",
            app_namespace="cart-agent",
            name="orders.read",
            category="Orders",
        )
        retrieved_perm = permission_repo.get_by_id(
            "tenant-1", "cart-agent", created_perm.id
        )
        assert retrieved_perm is not None
        assert retrieved_perm.id == created_perm.id
        assert retrieved_perm.name == "orders.read"

    def test_list_permissions_by_tenant(self, permission_repo):
        """Test listing permissions for a tenant."""
        permission_repo.create(
            tenant_id="tenant-2",
            app_namespace="cart-agent",
            name="perm1",
            category="Orders",
        )
        permission_repo.create(
            tenant_id="tenant-2",
            app_namespace="cart-agent",
            name="perm2",
            category="Products",
        )
        perms = permission_repo.list_by_tenant("tenant-2", "cart-agent")
        assert len(perms) >= 2

    def test_list_permissions_by_category(self, permission_repo):
        """Test listing permissions by category using GSI."""
        permission_repo.create(
            tenant_id="tenant-3",
            app_namespace="cart-agent",
            name="perm-a",
            category="Reports",
        )
        permission_repo.create(
            tenant_id="tenant-3",
            app_namespace="cart-agent",
            name="perm-b",
            category="Reports",
        )
        perms = permission_repo.list_by_category("Reports")
        assert len(perms) >= 2
        assert all(p.category == "Reports" for p in perms)

    def test_update_permission(self, permission_repo):
        """Test updating a permission."""
        created_perm = permission_repo.create(
            tenant_id="tenant-4",
            app_namespace="cart-agent",
            name="users.delete",
            category="Users",
        )
        updated_perm = permission_repo.update(
            "tenant-4",
            "cart-agent",
            created_perm.id,
            {"description": "Delete user accounts"},
        )
        assert updated_perm is not None
        assert updated_perm.description == "Delete user accounts"

    def test_delete_permission(self, permission_repo):
        """Test deleting a permission."""
        created_perm = permission_repo.create(
            tenant_id="tenant-5",
            app_namespace="cart-agent",
            name="temp.perm",
            category="Temp",
        )
        result = permission_repo.delete("tenant-5", "cart-agent", created_perm.id)
        assert result is True
        retrieved_perm = permission_repo.get_by_id(
            "tenant-5", "cart-agent", created_perm.id
        )
        assert retrieved_perm is None
