"""Tests for Tenant model and repository."""

import pytest
from moto import mock_dynamodb, mock_events
from boto3 import resource, client

from porth_common.models.tenant import Tenant
from porth_common.repositories.tenant_repo import TenantRepository


@pytest.fixture
def tenant_repo(dynamodb, dynamodb_tables, events_client):
    """Create a TenantRepository with mocked DynamoDB and EventBridge."""
    return TenantRepository(
        dynamodb_resource=dynamodb,
        events_client=events_client,
    )


class TestTenantModel:
    """Test Tenant Pydantic model."""

    def test_tenant_creation(self):
        """Test creating a Tenant instance."""
        tenant = Tenant(
            id="tenant-1",
            organization_id="org-1",
            name="Production Tenant",
            slug="prod-tenant",
            environment_type="production",
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert tenant.id == "tenant-1"
        assert tenant.name == "Production Tenant",
        assert tenant.environment_type == "production"
        assert tenant.status == "active"

    def test_tenant_validation_environment_type(self):
        """Test that invalid environment_type is rejected."""
        with pytest.raises(ValueError):
            Tenant(
                id="tenant-2",
                organization_id="org-1",
                name="Bad Tenant",
                slug="bad-tenant",
                environment_type="invalid",
                created_at="2026-03-09T10:00:00Z",
                updated_at="2026-03-09T10:00:00Z",
            )

    def test_tenant_validation_status(self):
        """Test that invalid status is rejected."""
        with pytest.raises(ValueError):
            Tenant(
                id="tenant-3",
                organization_id="org-1",
                name="Bad Status Tenant",
                slug="bad-status-tenant",
                environment_type="staging",
                status="deleted",
                created_at="2026-03-09T10:00:00Z",
                updated_at="2026-03-09T10:00:00Z",
            )


class TestTenantRepository:
    """Test TenantRepository CRUD operations."""

    def test_create_tenant(self, tenant_repo):
        """Test creating a tenant."""
        tenant = tenant_repo.create(
            organization_id="org-1",
            name="Test Tenant",
            slug="test-tenant",
            environment_type="staging",
        )
        assert tenant.id is not None
        assert tenant.name == "Test Tenant"
        assert tenant.environment_type == "staging"
        assert tenant.status == "active"

    def test_get_tenant_by_id(self, tenant_repo):
        """Test retrieving a tenant by ID."""
        created_tenant = tenant_repo.create(
            organization_id="org-2",
            name="Get Tenant",
            slug="get-tenant",
            environment_type="development",
        )
        retrieved_tenant = tenant_repo.get_by_id(created_tenant.id)
        assert retrieved_tenant is not None
        assert retrieved_tenant.id == created_tenant.id
        assert retrieved_tenant.name == "Get Tenant"

    def test_list_tenants_for_organization(self, tenant_repo):
        """Test listing tenants for an organization."""
        tenant_repo.create(
            organization_id="org-3",
            name="Tenant A",
            slug="tenant-a",
            environment_type="production",
        )
        tenant_repo.create(
            organization_id="org-3",
            name="Tenant B",
            slug="tenant-b",
            environment_type="staging",
        )
        tenants = tenant_repo.list_by_organization("org-3")
        assert len(tenants) >= 2
        assert all(t.organization_id == "org-3" for t in tenants)

    def test_update_tenant(self, tenant_repo):
        """Test updating a tenant."""
        created_tenant = tenant_repo.create(
            organization_id="org-4",
            name="Update Tenant",
            slug="update-tenant",
            environment_type="sandbox",
        )
        updated_tenant = tenant_repo.update(
            created_tenant.id,
            {"status": "suspended"},
        )
        assert updated_tenant.status == "suspended"
        assert updated_tenant.id == created_tenant.id

    def test_delete_tenant(self, tenant_repo):
        """Test deleting a tenant."""
        created_tenant = tenant_repo.create(
            organization_id="org-5",
            name="Delete Tenant",
            slug="delete-tenant",
            environment_type="development",
        )
        result = tenant_repo.delete(created_tenant.id)
        assert result is True
        retrieved_tenant = tenant_repo.get_by_id(created_tenant.id)
        assert retrieved_tenant is None
