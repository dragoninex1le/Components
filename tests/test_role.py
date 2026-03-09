"""Tests for Role, RolePermission, and UserRole models and repositories."""

import pytest
from porth_common.models.role import Role, RolePermission, UserRole
from porth_common.repositories.role_repo import RoleRepository, RolePermissionRepository, UserRoleRepository


@pytest.fixture
def role_repo(dynamodb, dynamodb_tables, events_client):
    """Create a RoleRepository with mocked DynamoDB and EventBridge."""
    return RoleRepository(
        dynamodb_resource=dynamodb,
        events_client=events_client,
    )


@pytest.fixture
def role_permission_repo(dynamodb, dynamodb_tables):
    """Create a RolePermissionRepository with mocked DynamoDB."""
    return RolePermissionRepository(dynamodb_resource=dynamodb)


@pytest.fixture
def user_role_repo(dynamodb, dynamodb_tables):
    """Create a UserRoleRepository with mocked DynamoDB."""
    return UserRoleRepository(dynamodb_resource=dynamodb)


class TestRoleModel:
    """Test Role Pydantic model."""

    def test_role_creation(self):
        """Test creating a Role instance."""
        role = Role(
            id="role-1",
            tenant_id="tenant-1",
            name="Admin",
            description="Administrator role",
            is_system=True,
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert role.id == "role-1"
        assert role.name == "Admin"
        assert role.is_system is True


class TestRoleRepository:
    """Test RoleRepository CRUD operations."""

    def test_create_role(self, role_repo):
        """Test creating a role."""
        role = role_repo.create(
            tenant_id="tenant-1",
            name="Editor",
            description="Editor role",
        )
        assert role.id is not None
        assert role.name == "Editor"
        assert role.is_system is False

    def test_get_role_by_id(self, role_repo):
        """Test retrieving a role by ID."""
        created = role_repo.create(
            tenant_id="tenant-1",
            name="Viewer",
        )
        retrieved = role_repo.get_by_id("tenant-1", created.id)
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_create_system_role(self, role_repo):
        """Test creating a system role that cannot be deleted."""
        role = role_repo.create_system_role(
            tenant_id="tenant-2",
            name="System Admin",
        )
        assert role.is_system is True
        # Verify it cannot be deleted
        with pytest.raises(ValueError):
            role_repo.delete("tenant-2", role.id)

    def test_list_roles_for_tenant(self, role_repo):
        """Test listing roles for a tenant."""
        role_repo.create(
            tenant_id="tenant-3",
            name="Role A",
        )
        role_repo.create(
            tenant_id="tenant-3",
            name="Role B",
        )
        roles = role_repo.list_by_tenant("tenant-3")
        assert len(roles) >= 2

    def test_delete_role(self, role_repo):
        """Test deleting a role."""
        created = role_repo.create(
            tenant_id="tenant-4",
            name="Temporary Role",
        )
        result = role_repo.delete("tenant-4", created.id)
        assert result is True


class TestRolePermissionRepository:
    """Test RolePermissionRepository."""

    def test_assign_permission_to_role(self, role_permission_repo):
        """Test assigning a permission to a role."""
        result = role_permission_repo.assign_permission(
            tenant_id="tenant-1",
            role_id="role-1",
            permission_key="users.read",
        )
        assert result is not None

    def test_get_role_permissions(self, role_permission_repo):
        """Test retrieving permissions for a role."""
        role_permission_repo.assign_permission(
            tenant_id="tenant-1",
            role_id="role-2",
            permission_key="users.read",
        )
        role_permission_repo.assign_permission(
            tenant_id="tenant-1",
            role_id="role-2",
            permission_key="users.write",
        )
        perms = role_permission_repo.get_role_permissions("tenant-1", "role-2")
        assert len(perms) >= 2


class TestUserRoleRepository:
    """Test UserRoleRepository."""

    def test_assign_role_to_user(self, user_role_repo):
        """Test assigning a role to a user."""
        result = user_role_repo.assign_role(
            tenant_id="tenant-1",
            user_id="user-1",
            role_id="role-1",
        )
        assert result is not None

    def test_get_user_roles(self, user_role_repo):
        """Test retrieving roles for a user."""
        user_role_repo.assign_role(
            tenant_id="tenant-1",
            user_id="user-2",
            role_id="role-1",
        )
        user_role_repo.assign_role(
            tenant_id="tenant-1",
            user_id="user-2",
            role_id="role-2",
        )
        roles = user_role_repo.get_user_roles("tenant-1", "user-2")
        assert len(roles) >= 2

    def test_revoke_role_from_user(self, user_role_repo):
        """Test revoking a role from a user."""
        user_role_repo.assign_role(
            tenant_id="tenant-1",
            user_id="user-3",
            role_id="role-3",
        )
        result = user_role_repo.revoke_role(
            tenant_id="tenant-1",
            user_id="user-3",
            role_id="role-3",
        )
        assert result is True
