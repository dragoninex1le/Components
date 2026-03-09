"""Tests for Organization model and repository."""

import pytest
from moto import mock_dynamodb, mock_events
from boto3 import resource, client

from porth_common.models.organization import Organization
from porth_common.repositories.organization_repo import OrganizationRepository


@pytest.fixture
def org_repo(dynamodb, dynamodb_tables):
    """Create an OrganizationRepository with mocked DynamoDB."""
    return OrganizationRepository(dynamodb_resource=dynamodb)


class TestOrganizationModel:
    """Test Organization Pydantic model."""

    def test_organization_creation(self):
        """Test creating an Organization instance."""
        org = Organization(
            id="org-1",
            name="Acme Corp",
            slug="acme-corp",
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert org.id == "org-1"
        assert org.name == "Acme Corp"
        assert org.slug == "acme-corp"
        assert org.status == "active"

    def test_organization_with_suspended_status(self):
        """Test creating an Organization with suspended status."""
        org = Organization(
            id="org-2",
            name="Old Corp",
            slug="old-corp",
            status="suspended",
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert org.status == "suspended"

    def test_organization_validation_invalid_status(self):
        """Test that invalid status is rejected."""
        with pytest.raises(ValueError):
            Organization(
                id="org-3",
                name="Bad Corp",
                slug="bad-corp",
                status="deleted",
                created_at="2026-03-09T10:00:00Z",
                updated_at="2026-03-09T10:00:00Z",
            )


class TestOrganizationRepository:
    """Test OrganizationRepository CRUD operations."""

    def test_create_organization(self, org_repo):
        """Test creating an organization."""
        org_data = {
            "name": "Test Org",
            "slug": "test-org",
            "company_details": {"industry": "tech"},
        }
        org = org_repo.create(org_data)
        assert org.id is not None
        assert org.name == "Test Org"
        assert org.slug == "test-org"
        assert org.status == "active"

    def test_get_organization_by_id(self, org_repo):
        """Test retrieving an organization by ID."""
        created_org = org_repo.create({
            "name": "Get Test Org",
            "slug": "get-test-org",
        })
        retrieved_org = org_repo.get_by_id(created_org.id)
        assert retrieved_org is not None
        assert retrieved_org.id == created_org.id
        assert retrieved_org.name == "Get Test Org"

    def test_get_organization_by_slug(self, org_repo):
        """Test retrieving an organization by slug using GSI."""
        created_org = org_repo.create({
            "name": "Slug Test Org",
            "slug": "slug-test-org",
        })
        retrieved_org = org_repo.get_by_slug("slug-test-org")
        assert retrieved_org is not None
        assert retrieved_org.id == created_org.id

    def test_update_organization(self, org_repo):
        """Test updating an organization."""
        created_org = org_repo.create({
            "name": "Update Test Org",
            "slug": "update-test-org",
        })
        updated_org = org_repo.update(created_org.id, {"name": "Updated Name"})
        assert updated_org.name == "Updated Name"
        assert updated_org.id == created_org.id

    def test_delete_organization(self, org_repo):
        """Test deleting an organization."""
        created_org = org_repo.create({
            "name": "Delete Test Org",
            "slug": "delete-test-org",
        })
        result = org_repo.delete(created_org.id)
        assert result is True
        retrieved_org = org_repo.get_by_id(created_org.id)
        assert retrieved_org is None

    def test_list_organizations(self, org_repo):
        """Test listing all organizations."""
        org_repo.create({"name": "List Org 1", "slug": "list-org-1"})
        org_repo.create({"name": "List Org 2", "slug": "list-org-2"})
        orgs = org_repo.list_all()
        assert len(orgs) >= 2
