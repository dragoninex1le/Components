"""Tests for ClaimRoleMapping model and repository."""

import pytest
from porth_common.models.claim_role_mapping import ClaimRoleMapping
from porth_common.repositories.claim_role_mapping_repo import ClaimRoleMappingRepository


@pytest.fixture
def claim_role_repo(dynamodb, dynamodb_tables, events_client):
    """Create a ClaimRoleMappingRepository with mocked DynamoDB and EventBridge."""
    return ClaimRoleMappingRepository(
        dynamodb_resource=dynamodb,
        events_client=events_client,
    )


class TestClaimRoleMappingModel:
    """Test ClaimRoleMapping Pydantic model."""

    def test_claim_role_mapping_creation(self):
        """Test creating a ClaimRoleMapping instance."""
        mapping = ClaimRoleMapping(
            id="mapping-1",
            tenant_id="tenant-1",
            app_namespace="cart-agent",
            claim_key="groups",
            claim_value="admin",
            role_id="role-admin",
            priority=10,
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert mapping.id == "mapping-1"
        assert mapping.claim_key == "groups"
        assert mapping.claim_value == "admin"
        assert mapping.priority == 10
        assert mapping.is_active is True

    def test_claim_role_mapping_with_custom_priority(self):
        """Test creating a ClaimRoleMapping with custom priority."""
        mapping = ClaimRoleMapping(
            id="mapping-2",
            tenant_id="tenant-1",
            app_namespace="cart-agent",
            claim_key="roles",
            claim_value="editor",
            role_id="role-editor",
            priority=5,
            is_active=False,
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert mapping.priority == 5
        assert mapping.is_active is False


class TestClaimRoleMappingRepository:
    """Test ClaimRoleMappingRepository CRUD operations."""

    def test_create_mapping(self, claim_role_repo):
        """Test creating a claim-to-role mapping."""
        mapping = claim_role_repo.create(
            tenant_id="tenant-1",
            app_namespace="cart-agent",
            claim_key="groups",
            claim_value="admin",
            role_id="role-admin",
            priority=10,
        )
        assert mapping.id is not None
        assert mapping.claim_key == "groups"
        assert mapping.claim_value == "admin"

    def test_get_mapping_by_id(self, claim_role_repo):
        """Test retrieving a mapping by ID."""
        created = claim_role_repo.create(
            tenant_id="tenant-2",
            app_namespace="cart-agent",
            claim_key="roles",
            claim_value="viewer",
            role_id="role-viewer",
        )
        retrieved = claim_role_repo.get_by_id(
            "tenant-2", "cart-agent", created.id
        )
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_list_mappings_by_tenant(self, claim_role_repo):
        """Test listing mappings for a tenant and namespace."""
        claim_role_repo.create(
            tenant_id="tenant-3",
            app_namespace="cart-agent",
            claim_key="groups",
            claim_value="users",
            role_id="role-user",
        )
        claim_role_repo.create(
            tenant_id="tenant-3",
            app_namespace="cart-agent",
            claim_key="groups",
            claim_value="admins",
            role_id="role-admin",
        )
        mappings = claim_role_repo.list_by_tenant("tenant-3", "cart-agent")
        assert len(mappings) >= 2

    def test_update_mapping(self, claim_role_repo):
        """Test updating a mapping."""
        created = claim_role_repo.create(
            tenant_id="tenant-4",
            app_namespace="cart-agent",
            claim_key="department",
            claim_value="sales",
            role_id="role-sales",
            priority=0,
        )
        updated = claim_role_repo.update(
            "tenant-4",
            "cart-agent",
            created.id,
            {"priority": 20, "is_active": False},
        )
        assert updated.priority == 20
        assert updated.is_active is False

    def test_delete_mapping(self, claim_role_repo):
        """Test deleting a mapping."""
        created = claim_role_repo.create(
            tenant_id="tenant-5",
            app_namespace="cart-agent",
            claim_key="temp",
            claim_value="temp",
            role_id="role-temp",
        )
        result = claim_role_repo.delete("tenant-5", "cart-agent", created.id)
        assert result is True
