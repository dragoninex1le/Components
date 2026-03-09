"""Tests for User model and repository."""

import pytest
from porth_common.models.user import User
from porth_common.repositories.user_repo import UserRepository


@pytest.fixture
def user_repo(dynamodb, dynamodb_tables, events_client):
    """Create a UserRepository with mocked DynamoDB and EventBridge."""
    return UserRepository(
        dynamodb_resource=dynamodb,
        events_client=events_client,
    )


class TestUserModel:
    """Test User Pydantic model."""

    def test_user_creation(self):
        """Test creating a User instance."""
        user = User(
            id="user-1",
            external_id="auth0|12345",
            email="john@example.com",
            organization_id="org-1",
            tenant_id="tenant-1",
            first_name="John",
            last_name="Doe",
            created_at="2026-03-09T10:00:00Z",
            updated_at="2026-03-09T10:00:00Z",
        )
        assert user.id == "user-1"
        assert user.email == "john@example.com"
        assert user.status == "active"

    def test_user_validation_invalid_status(self):
        """Test that invalid status is rejected."""
        with pytest.raises(ValueError):
            User(
                id="user-2",
                external_id="auth0|67890",
                email="jane@example.com",
                organization_id="org-1",
                tenant_id="tenant-1",
                status="deleted",
                created_at="2026-03-09T10:00:00Z",
                updated_at="2026-03-09T10:00:00Z",
            )


class TestUserRepository:
    """Test UserRepository CRUD operations."""

    def test_create_user(self, user_repo):
        """Test creating a user."""
        user = user_repo.create(
            external_id="auth0|user1",
            email="test@example.com",
            organization_id="org-1",
            tenant_id="tenant-1",
            first_name="Test",
            last_name="User",
        )
        assert user.id is not None
        assert user.email == "test@example.com"
        assert user.status == "active"

    def test_get_user_by_id(self, user_repo):
        """Test retrieving a user by ID."""
        created = user_repo.create(
            external_id="auth0|user2",
            email="get@example.com",
            organization_id="org-1",
            tenant_id="tenant-1",
        )
        retrieved = user_repo.get_by_id(created.id)
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.email == "get@example.com"

    def test_get_user_by_external_id(self, user_repo):
        """Test retrieving a user by external ID."""
        created = user_repo.create(
            external_id="auth0|user3",
            email="external@example.com",
            organization_id="org-1",
            tenant_id="tenant-1",
        )
        retrieved = user_repo.get_by_external_id("auth0|user3")
        assert retrieved is not None
        assert retrieved.id == created.id

    def test_list_users_for_tenant(self, user_repo):
        """Test listing users for a tenant."""
        user_repo.create(
            external_id="auth0|user4",
            email="user4@example.com",
            organization_id="org-1",
            tenant_id="tenant-2",
        )
        user_repo.create(
            external_id="auth0|user5",
            email="user5@example.com",
            organization_id="org-1",
            tenant_id="tenant-2",
        )
        users = user_repo.list_by_tenant("tenant-2")
        assert len(users) >= 2

    def test_update_user(self, user_repo):
        """Test updating a user."""
        created = user_repo.create(
            external_id="auth0|user6",
            email="update@example.com",
            organization_id="org-1",
            tenant_id="tenant-1",
        )
        updated = user_repo.update(
            created.id,
            {"first_name": "Updated", "last_name": "User"},
        )
        assert updated.first_name == "Updated"
        assert updated.last_name == "User"

    def test_delete_user(self, user_repo):
        """Test deleting a user."""
        created = user_repo.create(
            external_id="auth0|user7",
            email="delete@example.com",
            organization_id="org-1",
            tenant_id="tenant-1",
        )
        result = user_repo.delete(created.id)
        assert result is True
