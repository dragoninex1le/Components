"""Unit tests for Organization entity and repository."""

from __future__ import annotations

import pytest

from porth_common.events.publisher import EventPublisher
from porth_common.models.organization import Organization
from porth_common.repositories.organization_repo import OrganizationRepository
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
def org_repo(dynamodb_resource, events_client, porth_users_table):
    """Create an OrganizationRepository instance for testing."""
    event_publisher = EventPublisher(
        event_bus_name="porth-events",
        client=events_client,
    )
    return OrganizationRepository(
        table_name="porth-users",
        dynamodb_resource=dynamodb_resource,
        event_publisher=event_publisher,
    )


class TestOrganizationModel:
    """Test Organization Pydantic model."""

    def test_organization_creation_minimal(self):
        """Test creating an Organization with only required fields."""
        org = Organization(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Acme Corp",
            slug="acme-corp",
            created_at="2026-03-09T10:00:00+00:00",
            updated_at="2026-03-09T10:00:00+00:00",
        )

        assert org.id == "550e8400-e29b-41d4-a716-446655440000"
        assert org.name == "Acme Corp"
        assert org.slug == "acme-corp"
        assert org.status == "active"
        assert org.created_at == "2026-03-09T10:00:00+00:00"
        assert org.updated_at == "2026-03-09T10:00:00+00:00"

    def test_organization_creation_full(self):
        """Test creating an Organization with all fields."""
        org = Organization(
            id="550e8400-e29b-41d4-a716-446655440000",
            name="Acme Corp",
            slug="acme-corp",
            status="active",
            company_details={"legal_name": "Acme Corporation Inc.", "registration": "12345"},
            addresses=[{"type": "headquarters", "city": "New York"}],
            billing_config={"currency": "USD"},
            idp_config={"issuer": "https://idp.example.com", "client_id": "client-123"},
            settings={"feature_x": True},
            created_at="2026-03-09T10:00:00+00:00",
            updated_at="2026-03-09T10:00:00+00:00",
        )

        assert org.name == "Acme Corp"
        assert org.status == "active"
        assert org.company_details["legal_name"] == "Acme Corporation Inc."
        assert len(org.addresses) == 1
        assert org.billing_config["currency"] == "USD"
        assert org.idp_config["issuer"] == "https://idp.example.com"
        assert org.settings["feature_x"] is True

    def test_organization_status_validation(self):
        """Test that status is validated."""
        with pytest.raises(ValueError):
            Organization(
                id="test-id",
                name="Test",
                slug="test",
                status="invalid",
                created_at="2026-03-09T10:00:00+00:00",
                updated_at="2026-03-09T10:00:00+00:00",
            )


class TestOrganizationRepository:
    """Test OrganizationRepository CRUD operations."""

    def test_create_organization(self, org_repo):
        """Test creating a new organization."""
        org = org_repo.create({
            "name": "Test Org",
            "slug": "test-org",
            "status": "active",
        })

        assert org.id is not None
        assert org.name == "Test Org"
        assert org.slug == "test-org"
        assert org.status == "active"
        assert org.created_at is not None
        assert org.updated_at is not None

    def test_get_organization_by_id(self, org_repo):
        """Test retrieving an organization by ID."""
        created_org = org_repo.create({
            "name": "Test Org",
            "slug": "test-org",
        })

        retrieved_org = org_repo.get_by_id(created_org.id)

        assert retrieved_org is not None
        assert retrieved_org.id == created_org.id
        assert retrieved_org.name == "Test Org"
        assert retrieved_org.slug == "test-org"

    def test_get_organization_by_id_not_found(self, org_repo):
        """Test retrieving a non-existent organization returns None."""
        result = org_repo.get_by_id("nonexistent-id")
        assert result is None

    def test_get_organization_by_slug(self, org_repo):
        """Test retrieving an organization by slug."""
        created_org = org_repo.create({
            "name": "Test Org",
            "slug": "test-org",
        })

        retrieved_org = org_repo.get_by_slug("test-org")

        assert retrieved_org is not None
        assert retrieved_org.id == created_org.id
        assert retrieved_org.name == "Test Org"

    def test_get_organization_by_slug_not_found(self, org_repo):
        """Test retrieving a non-existent organization by slug returns None."""
        result = org_repo.get_by_slug("nonexistent-slug")
        assert result is None

    def test_update_organization(self, org_repo):
        """Test updating an organization."""
        created_org = org_repo.create({
            "name": "Test Org",
            "slug": "test-org",
        })

        updated_org = org_repo.update(created_org.id, {
            "name": "Updated Test Org",
        })

        assert updated_org is not None
        assert updated_org.id == created_org.id
        assert updated_org.name == "Updated Test Org"
        assert updated_org.slug == "test-org"
        assert updated_org.updated_at > created_org.updated_at

    def test_update_organization_not_found(self, org_repo):
        """Test updating a non-existent organization returns None."""
        result = org_repo.update("nonexistent-id", {"name": "New Name"})
        assert result is None

    def test_update_organization_slug(self, org_repo):
        """Test updating organization slug updates GSI."""
        created_org = org_repo.create({
            "name": "Test Org",
            "slug": "test-org",
        })

        updated_org = org_repo.update(created_org.id, {
            "slug": "new-slug",
        })

        assert updated_org.slug == "new-slug"

        # Verify old slug no longer works
        old_result = org_repo.get_by_slug("test-org")
        assert old_result is None

        # Verify new slug works
        new_result = org_repo.get_by_slug("new-slug")
        assert new_result is not None
        assert new_result.id == created_org.id

    def test_list_all_organizations(self, org_repo):
        """Test listing all organizations."""
        org1 = org_repo.create({"name": "Org 1", "slug": "org-1"})
        org2 = org_repo.create({"name": "Org 2", "slug": "org-2"})
        org3 = org_repo.create({"name": "Org 3", "slug": "org-3"})

        orgs = org_repo.list_all()

        assert len(orgs) == 3
        org_ids = {org.id for org in orgs}
        assert org1.id in org_ids
        assert org2.id in org_ids
        assert org3.id in org_ids

    def test_create_organization_with_nested_data(self, org_repo):
        """Test creating an organization with nested configuration."""
        org = org_repo.create({
            "name": "Enterprise Org",
            "slug": "enterprise-org",
            "company_details": {
                "legal_name": "Enterprise Inc.",
                "registration_number": "REG-12345",
                "country": "US",
            },
            "idp_config": {
                "issuer": "https://auth.example.com",
                "client_id": "client-xyz",
                "audience": "https://api.example.com",
                "jwks_uri": "https://auth.example.com/.well-known/jwks.json",
            },
            "settings": {
                "enable_saml": True,
                "session_timeout_minutes": 60,
            },
        })

        retrieved = org_repo.get_by_id(org.id)

        assert retrieved.company_details["legal_name"] == "Enterprise Inc."
        assert retrieved.idp_config["issuer"] == "https://auth.example.com"
        assert retrieved.settings["enable_saml"] is True

    def test_organization_sequential_ids(self, org_repo):
        """Test that organization IDs are sequential integers starting at 1000."""
        org1 = org_repo.create({"name": "First Org", "slug": "first-org"})
        org2 = org_repo.create({"name": "Second Org", "slug": "second-org"})
        org3 = org_repo.create({"name": "Third Org", "slug": "third-org"})

        assert org1.id == "1000"
        assert org2.id == "1001"
        assert org3.id == "1002"

        # Verify all three are retrievable by their sequential IDs
        assert org_repo.get_by_id("1000").name == "First Org"
        assert org_repo.get_by_id("1001").name == "Second Org"
        assert org_repo.get_by_id("1002").name == "Third Org"

    def test_organization_status_transition(self, org_repo):
        """Test transitioning organization status."""
        org = org_repo.create({
            "name": "Test Org",
            "slug": "test-org",
            "status": "active",
        })

        assert org.status == "active"

        suspended = org_repo.update(org.id, {"status": "suspended"})

        assert suspended.status == "suspended"

        reactivated = org_repo.update(suspended.id, {"status": "active"})

        assert reactivated.status == "active"
