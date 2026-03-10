"""Unit tests for Tenant entity and repository."""

from __future__ import annotations

import pytest

from porth_common.events.publisher import EventPublisher
from porth_common.models.tenant import Tenant
from porth_common.repositories.tenant_repo import TenantRepository
from tests.conftest import create_table


@pytest.fixture
def porth_users_table(dynamodb_resource):
    """Create the porth-users table for testing."""
    create_table(
        dynamodb_resource,
        "porth-users",
        key_schema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        attribute_definitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "gsi1pk", "AttributeType": "S"},
            {"AttributeName": "gsi1sk", "AttributeType": "S"},
        ],
        gsis=[
            {
                "IndexName": "gsi1",
                "KeySchema": [
                    {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                    {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )


@pytest.fixture
def tenant_repo(dynamodb_resource, events_client, porth_users_table):
    """Create a TenantRepository instance for testing."""
    event_publisher = EventPublisher(
        event_bus_name="porth-events",
        client=events_client,
    )
    return TenantRepository(
        table_name="porth-users",
        dynamodb_resource=dynamodb_resource,
        event_publisher=event_publisher,
    )


class TestTenantModel:
    """Test Tenant Pydantic model."""

    def test_tenant_creation_minimal(self):
        """Test creating a Tenant with only required fields."""
        tenant = Tenant(
            id="550e8400-e29b-41d4-a716-446655440000",
            organization_id="org-123",
            name="Production Tenant",
            slug="prod",
            environment_type="production",
            created_at="2026-03-09T10:00:00+00:00",
            updated_at="2026-03-09T10:00:00+00:00",
        )

        assert tenant.id == "550e8400-e29b-41d4-a716-446655440000"
        assert tenant.organization_id == "org-123"
        assert tenant.name == "Production Tenant"
        assert tenant.slug == "prod"
        assert tenant.environment_type == "production"
        assert tenant.status == "active"

    def test_tenant_creation_full(self):
        """Test creating a Tenant with all fields."""
        tenant = Tenant(
            id="550e8400-e29b-41d4-a716-446655440000",
            organization_id="org-123",
            name="Staging Tenant",
            slug="staging",
            environment_type="staging",
            status="active",
            settings={"feature_x": True},
            feature_flags={"new_feature": False},
            idp_config_override={
                "issuer": "https://staging-idp.example.com",
                "client_id": "staging-client",
                "audience": "https://staging-api.example.com",
            },
            created_at="2026-03-09T10:00:00+00:00",
            updated_at="2026-03-09T10:00:00+00:00",
        )

        assert tenant.name == "Staging Tenant"
        assert tenant.environment_type == "staging"
        assert tenant.settings["feature_x"] is True
        assert tenant.feature_flags["new_feature"] is False
        assert tenant.idp_config_override["issuer"] == "https://staging-idp.example.com"

    def test_tenant_environment_type_validation(self):
        """Test that environment_type is validated."""
        with pytest.raises(ValueError):
            Tenant(
                id="test-id",
                organization_id="org-123",
                name="Test",
                slug="test",
                environment_type="invalid",
                created_at="2026-03-09T10:00:00+00:00",
                updated_at="2026-03-09T10:00:00+00:00",
            )

    def test_tenant_status_validation(self):
        """Test that status is validated."""
        with pytest.raises(ValueError):
            Tenant(
                id="test-id",
                organization_id="org-123",
                name="Test",
                slug="test",
                environment_type="production",
                status="invalid",
                created_at="2026-03-09T10:00:00+00:00",
                updated_at="2026-03-09T10:00:00+00:00",
            )


class TestTenantRepository:
    """Test TenantRepository CRUD operations."""

    def test_tenant_sequential_ids(self, tenant_repo):
        """Test that tenant IDs are sequential integers starting at 1000."""
        t1 = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Prod", "slug": "prod", "environment_type": "production",
        })
        t2 = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Staging", "slug": "staging", "environment_type": "staging",
        })

        assert t1.id == "1000"
        assert t2.id == "1001"

        assert tenant_repo.get_by_id("1000").name == "Prod"
        assert tenant_repo.get_by_id("1001").name == "Staging"

    def test_create_tenant(self, tenant_repo):
        """Test creating a new tenant."""
        tenant = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Production",
            "slug": "prod",
            "environment_type": "production",
        })

        assert tenant.id is not None
        assert tenant.organization_id == "org-123"
        assert tenant.name == "Production"
        assert tenant.slug == "prod"
        assert tenant.environment_type == "production"
        assert tenant.status == "active"

    def test_get_tenant_by_id(self, tenant_repo):
        """Test retrieving a tenant by ID."""
        created_tenant = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Test Tenant",
            "slug": "test",
            "environment_type": "development",
        })

        retrieved_tenant = tenant_repo.get_by_id(created_tenant.id)

        assert retrieved_tenant is not None
        assert retrieved_tenant.id == created_tenant.id
        assert retrieved_tenant.name == "Test Tenant"
        assert retrieved_tenant.environment_type == "development"

    def test_get_tenant_by_id_not_found(self, tenant_repo):
        """Test retrieving a non-existent tenant returns None."""
        result = tenant_repo.get_by_id("nonexistent-id")
        assert result is None

    def test_list_tenants_by_org(self, tenant_repo):
        """Test listing all tenants for an organization."""
        org_id = "org-123"

        tenant1 = tenant_repo.create({
            "organization_id": org_id,
            "name": "Production",
            "slug": "prod",
            "environment_type": "production",
        })

        tenant2 = tenant_repo.create({
            "organization_id": org_id,
            "name": "Staging",
            "slug": "staging",
            "environment_type": "staging",
        })

        tenant3 = tenant_repo.create({
            "organization_id": org_id,
            "name": "Development",
            "slug": "dev",
            "environment_type": "development",
        })

        # Create a tenant in a different org (should not be included)
        tenant_repo.create({
            "organization_id": "org-456",
            "name": "Other Org Tenant",
            "slug": "other",
            "environment_type": "production",
        })

        tenants = tenant_repo.list_by_org(org_id)

        assert len(tenants) == 3
        tenant_ids = {t.id for t in tenants}
        assert tenant1.id in tenant_ids
        assert tenant2.id in tenant_ids
        assert tenant3.id in tenant_ids

    def test_list_tenants_by_org_empty(self, tenant_repo):
        """Test listing tenants for an organization with no tenants."""
        tenants = tenant_repo.list_by_org("nonexistent-org")
        assert len(tenants) == 0

    def test_update_tenant(self, tenant_repo):
        """Test updating a tenant."""
        created_tenant = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Production",
            "slug": "prod",
            "environment_type": "production",
        })

        updated_tenant = tenant_repo.update(created_tenant.id, {
            "name": "Updated Production",
            "status": "suspended",
        })

        assert updated_tenant is not None
        assert updated_tenant.id == created_tenant.id
        assert updated_tenant.name == "Updated Production"
        assert updated_tenant.status == "suspended"
        assert updated_tenant.slug == "prod"
        assert updated_tenant.updated_at > created_tenant.updated_at

    def test_update_tenant_not_found(self, tenant_repo):
        """Test updating a non-existent tenant returns None."""
        result = tenant_repo.update("nonexistent-id", {"name": "New Name"})
        assert result is None

    def test_tenant_with_idp_config_override(self, tenant_repo):
        """Test tenant with IdP configuration override."""
        idp_override = {
            "issuer": "https://staging-idp.example.com",
            "client_id": "staging-client-id",
            "audience": "https://staging-api.example.com",
        }

        tenant = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Staging",
            "slug": "staging",
            "environment_type": "staging",
            "idp_config_override": idp_override,
        })

        retrieved = tenant_repo.get_by_id(tenant.id)

        assert retrieved.idp_config_override == idp_override
        assert retrieved.idp_config_override["issuer"] == "https://staging-idp.example.com"

    def test_tenant_without_idp_config_override(self, tenant_repo):
        """Test tenant without IdP override (falls back to org-level)."""
        tenant = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Production",
            "slug": "prod",
            "environment_type": "production",
        })

        retrieved = tenant_repo.get_by_id(tenant.id)

        assert retrieved.idp_config_override is None

    def test_tenant_feature_flags(self, tenant_repo):
        """Test tenant with feature flags."""
        flags = {
            "new_ui": True,
            "beta_feature": False,
            "experimental_api": True,
        }

        tenant = tenant_repo.create({
            "organization_id": "org-123",
            "name": "Test",
            "slug": "test",
            "environment_type": "development",
            "feature_flags": flags,
        })

        retrieved = tenant_repo.get_by_id(tenant.id)

        assert retrieved.feature_flags == flags
        assert retrieved.feature_flags["new_ui"] is True
        assert retrieved.feature_flags["beta_feature"] is False

    def test_update_tenant_status_provisioning(self, tenant_repo):
        """Test updating tenant status through provisioning."""
        tenant = tenant_repo.create({
            "organization_id": "org-123",
            "name": "New Tenant",
            "slug": "new",
            "environment_type": "production",
            "status": "provisioning",
        })

        assert tenant.status == "provisioning"

        # Simulate provisioning completion
        completed = tenant_repo.update(tenant.id, {"status": "active"})

        assert completed.status == "active"

    def test_multiple_tenants_multiple_environments(self, tenant_repo):
        """Test organization with multiple tenants across all environment types."""
        org_id = "org-multi-env"

        prod = tenant_repo.create({
            "organization_id": org_id,
            "name": "Production",
            "slug": "prod",
            "environment_type": "production",
        })

        staging = tenant_repo.create({
            "organization_id": org_id,
            "name": "Staging",
            "slug": "staging",
            "environment_type": "staging",
        })

        dev = tenant_repo.create({
            "organization_id": org_id,
            "name": "Development",
            "slug": "dev",
            "environment_type": "development",
        })

        sandbox = tenant_repo.create({
            "organization_id": org_id,
            "name": "Sandbox",
            "slug": "sandbox",
            "environment_type": "sandbox",
        })

        tenants = tenant_repo.list_by_org(org_id)

        assert len(tenants) == 4
        env_types = {t.environment_type for t in tenants}
        assert env_types == {"production", "staging", "development", "sandbox"}
