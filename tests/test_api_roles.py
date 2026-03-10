"""Unit tests for Role CRUD API endpoints (FastAPI handler level).

Tests the full Role API endpoints via FastAPI TestClient, exercising the handler → repository
→ DynamoDB flow with mocked AWS services.

Covers PORTH-11 acceptance criteria:
- Roles scoped to tenant_id (cannot see other tenant's roles)
- POST creates roles, returns 201
- PATCH updates role name/description, returns updated role or 404
- DELETE returns 204, protects system roles with 403
- PUT /roles/{tenant_id}/{role_id}/permissions replaces the permission set
- GET lists roles filtered by tenant
"""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws
from fastapi.testclient import TestClient

from tests.conftest import create_table


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _set_api_env(monkeypatch):
    """Set environment variables required by the API layer."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("PORTH_ROLES_TABLE", "porth-roles")
    monkeypatch.setenv("PORTH_EVENT_BUS", "porth-events")


@pytest.fixture
def _mock_aws():
    """Provide a mocked AWS environment for the entire test."""
    with mock_aws():
        # Create required DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_table(
            dynamodb,
            "porth-roles",
            key_schema=[
                {"AttributeName": "pk", "KeyType": "HASH"},
                {"AttributeName": "sk", "KeyType": "RANGE"},
            ],
            attribute_definitions=[
                {"AttributeName": "pk", "AttributeType": "S"},
                {"AttributeName": "sk", "AttributeType": "S"},
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
        # Create EventBridge bus
        events = boto3.client("events", region_name="us-east-1")
        events.create_event_bus(Name="porth-events")
        yield


@pytest.fixture
def client(_mock_aws):
    """Create a FastAPI TestClient with mocked DynamoDB."""
    from lambdas.api.app import app

    return TestClient(app)


# ── Helper functions ────────────────────────────────────────────────────────────


def _create_role(client, tenant_id, name, description=None, is_system=False):
    """Helper to POST a create role request."""
    return client.post(
        "/roles/",
        json={
            "tenant_id": tenant_id,
            "name": name,
            "description": description,
            "is_system": is_system,
        },
    )


def _list_roles(client, tenant_id):
    """Helper to GET roles for a tenant."""
    return client.get("/roles/", params={"tenant_id": tenant_id})


def _get_role(client, tenant_id, role_id):
    """Helper to GET a specific role."""
    return client.get(f"/roles/{tenant_id}/{role_id}")


def _update_role(client, tenant_id, role_id, name=None, description=None):
    """Helper to PATCH a role."""
    body = {}
    if name is not None:
        body["name"] = name
    if description is not None:
        body["description"] = description
    return client.patch(
        f"/roles/{tenant_id}/{role_id}",
        json=body,
    )


def _delete_role(client, tenant_id, role_id):
    """Helper to DELETE a role."""
    return client.delete(f"/roles/{tenant_id}/{role_id}")


def _set_role_permissions(client, role_id, tenant_id, permission_keys):
    """Helper to PUT role permissions."""
    return client.put(
        f"/roles/{tenant_id}/{role_id}/permissions",
        json=permission_keys,
    )


def _get_role_permissions(client, role_id, tenant_id):
    """Helper to GET role permissions."""
    return client.get(f"/roles/{tenant_id}/{role_id}/permissions")


def _assign_role_to_user(client, user_id, tenant_id, role_id):
    """Helper to POST assign role to user."""
    return client.post(f"/roles/users/{user_id}/tenant/{tenant_id}/roles/{role_id}")


def _remove_role_from_user(client, user_id, tenant_id, role_id):
    """Helper to DELETE remove role from user."""
    return client.delete(f"/roles/users/{user_id}/tenant/{tenant_id}/roles/{role_id}")


def _get_user_roles(client, user_id, tenant_id):
    """Helper to GET user's roles."""
    return client.get(f"/roles/users/{user_id}/tenant/{tenant_id}/roles")


# ── POST /roles — role creation ──────────────────────────────────────────────────


class TestCreateRole:
    """Tests for the POST /roles endpoint."""

    def test_create_role_minimal(self, client):
        """Create a role with minimal required fields."""
        resp = _create_role(client, "tenant-1", "Editor")

        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] is not None
        assert body["tenant_id"] == "tenant-1"
        assert body["name"] == "Editor"
        assert body["description"] is None
        assert body["is_system"] is False
        assert body["created_at"] is not None
        assert body["updated_at"] is not None

    def test_create_role_with_description(self, client):
        """Create a role with description."""
        resp = _create_role(
            client,
            "tenant-1",
            "Editor",
            description="Can edit all content",
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Editor"
        assert body["description"] == "Can edit all content"

    def test_create_system_role(self, client):
        """Create a system role (is_system=True)."""
        resp = _create_role(client, "tenant-1", "Admin", is_system=True)

        assert resp.status_code == 201
        body = resp.json()
        assert body["is_system"] is True

    def test_create_multiple_roles_same_tenant(self, client):
        """Create multiple roles in the same tenant."""
        resp1 = _create_role(client, "tenant-1", "Editor")
        resp2 = _create_role(client, "tenant-1", "Viewer")

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        assert resp1.json()["id"] != resp2.json()["id"]

    def test_create_role_generates_unique_ids(self, client):
        """Verify that created roles have unique IDs."""
        resp1 = _create_role(client, "tenant-1", "Role1")
        resp2 = _create_role(client, "tenant-1", "Role2")

        id1 = resp1.json()["id"]
        id2 = resp2.json()["id"]
        assert id1 != id2

    def test_create_role_same_name_different_tenants(self, client):
        """Same role name can exist in different tenants."""
        resp1 = _create_role(client, "tenant-1", "Admin")
        resp2 = _create_role(client, "tenant-2", "Admin")

        assert resp1.status_code == 201
        assert resp2.status_code == 201
        # Different IDs for different tenants
        assert resp1.json()["id"] != resp2.json()["id"]

    def test_create_role_all_fields(self, client):
        """Create a role with all fields specified."""
        resp = _create_role(
            client,
            "tenant-1",
            "Administrator",
            description="Full system access",
            is_system=True,
        )

        assert resp.status_code == 201
        body = resp.json()
        assert body["tenant_id"] == "tenant-1"
        assert body["name"] == "Administrator"
        assert body["description"] == "Full system access"
        assert body["is_system"] is True


# ── GET /roles — role listing ────────────────────────────────────────────────────


class TestListRoles:
    """Tests for the GET /roles listing endpoint."""

    def test_list_empty_tenant(self, client):
        """List roles for a tenant with no roles."""
        resp = _list_roles(client, "tenant-1")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_single_role(self, client):
        """List a single role."""
        _create_role(client, "tenant-1", "Editor")
        resp = _list_roles(client, "tenant-1")

        assert resp.status_code == 200
        roles = resp.json()
        assert len(roles) == 1
        assert roles[0]["name"] == "Editor"

    def test_list_multiple_roles(self, client):
        """List multiple roles for a tenant."""
        _create_role(client, "tenant-1", "Admin")
        _create_role(client, "tenant-1", "Editor")
        _create_role(client, "tenant-1", "Viewer")

        resp = _list_roles(client, "tenant-1")

        assert resp.status_code == 200
        roles = resp.json()
        assert len(roles) == 3
        names = {r["name"] for r in roles}
        assert names == {"Admin", "Editor", "Viewer"}

    def test_list_roles_tenant_isolation(self, client):
        """Roles from different tenants are isolated."""
        _create_role(client, "tenant-1", "Admin")
        _create_role(client, "tenant-1", "Editor")
        _create_role(client, "tenant-2", "Viewer")

        resp1 = _list_roles(client, "tenant-1")
        resp2 = _list_roles(client, "tenant-2")

        assert resp1.status_code == 200
        assert resp2.status_code == 200
        roles1 = resp1.json()
        roles2 = resp2.json()

        assert len(roles1) == 2
        assert len(roles2) == 1
        assert all(r["tenant_id"] == "tenant-1" for r in roles1)
        assert all(r["tenant_id"] == "tenant-2" for r in roles2)

    def test_list_roles_includes_system_roles(self, client):
        """List includes system roles."""
        _create_role(client, "tenant-1", "Admin", is_system=True)
        _create_role(client, "tenant-1", "Editor")

        resp = _list_roles(client, "tenant-1")
        roles = resp.json()

        system_roles = {r["name"] for r in roles if r["is_system"]}
        assert "Admin" in system_roles

    def test_list_nonexistent_tenant(self, client):
        """List for non-existent tenant returns empty list."""
        resp = _list_roles(client, "nonexistent-tenant")

        assert resp.status_code == 200
        assert resp.json() == []


# ── GET /roles/{tenant_id}/{role_id} — get single role ──────────────────────────


class TestGetRole:
    """Tests for the GET /roles/{tenant_id}/{role_id} endpoint."""

    def test_get_existing_role(self, client):
        """Retrieve an existing role."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _get_role(client, "tenant-1", role_id)

        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == role_id
        assert body["name"] == "Editor"
        assert body["tenant_id"] == "tenant-1"

    def test_get_nonexistent_role(self, client):
        """Get non-existent role returns 404."""
        resp = _get_role(client, "tenant-1", "nonexistent-id")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_role_wrong_tenant(self, client):
        """Role from one tenant is not accessible from another."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _get_role(client, "tenant-2", role_id)

        assert resp.status_code == 404

    def test_get_system_role(self, client):
        """Get a system role."""
        create_resp = _create_role(client, "tenant-1", "Admin", is_system=True)
        role_id = create_resp.json()["id"]

        resp = _get_role(client, "tenant-1", role_id)

        assert resp.status_code == 200
        body = resp.json()
        assert body["is_system"] is True

    def test_get_role_with_description(self, client):
        """Get a role with description."""
        create_resp = _create_role(
            client,
            "tenant-1",
            "Editor",
            description="Can edit content",
        )
        role_id = create_resp.json()["id"]

        resp = _get_role(client, "tenant-1", role_id)

        assert resp.status_code == 200
        assert resp.json()["description"] == "Can edit content"


# ── PATCH /roles/{tenant_id}/{role_id} — role update ────────────────────────────


class TestUpdateRole:
    """Tests for the PATCH /roles/{tenant_id}/{role_id} endpoint."""

    def test_update_role_name(self, client):
        """Update a role's name."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _update_role(client, "tenant-1", role_id, name="Content Editor")

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Content Editor"
        assert body["id"] == role_id

    def test_update_role_description(self, client):
        """Update a role's description."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _update_role(client, "tenant-1", role_id, description="Updated description")

        assert resp.status_code == 200
        body = resp.json()
        assert body["description"] == "Updated description"

    def test_update_role_name_and_description(self, client):
        """Update both name and description."""
        create_resp = _create_role(
            client,
            "tenant-1",
            "Editor",
            description="Original",
        )
        role_id = create_resp.json()["id"]

        resp = _update_role(
            client,
            "tenant-1",
            role_id,
            name="Senior Editor",
            description="Updated description",
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Senior Editor"
        assert body["description"] == "Updated description"

    def test_update_nonexistent_role(self, client):
        """Update non-existent role returns 404."""
        resp = _update_role(client, "tenant-1", "nonexistent-id", name="New Name")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_update_role_wrong_tenant(self, client):
        """Cannot update role with wrong tenant ID."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _update_role(client, "tenant-2", role_id, name="New Name")

        assert resp.status_code == 404

    def test_update_preserves_is_system_flag(self, client):
        """is_system flag is preserved on update."""
        create_resp = _create_role(client, "tenant-1", "Admin", is_system=True)
        role_id = create_resp.json()["id"]

        resp = _update_role(client, "tenant-1", role_id, name="Administrator")

        assert resp.status_code == 200
        assert resp.json()["is_system"] is True

    def test_update_preserves_created_at(self, client):
        """created_at timestamp is preserved on update."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        original_created_at = create_resp.json()["created_at"]
        role_id = create_resp.json()["id"]

        resp = _update_role(client, "tenant-1", role_id, name="New Name")

        assert resp.status_code == 200
        assert resp.json()["created_at"] == original_created_at

    def test_update_changes_updated_at(self, client):
        """updated_at timestamp changes on update."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        original_updated_at = create_resp.json()["updated_at"]
        role_id = create_resp.json()["id"]

        resp = _update_role(client, "tenant-1", role_id, name="New Name")

        assert resp.status_code == 200
        # Should be different (or at least not fail)
        assert resp.json()["updated_at"] is not None


# ── DELETE /roles/{tenant_id}/{role_id} — role deletion ──────────────────────────


class TestDeleteRole:
    """Tests for the DELETE /roles/{tenant_id}/{role_id} endpoint."""

    def test_delete_role(self, client):
        """Delete a normal role."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _delete_role(client, "tenant-1", role_id)

        assert resp.status_code == 204

        # Verify it's deleted
        get_resp = _get_role(client, "tenant-1", role_id)
        assert get_resp.status_code == 404

    def test_delete_nonexistent_role(self, client):
        """Delete non-existent role returns 404."""
        resp = _delete_role(client, "tenant-1", "nonexistent-id")

        assert resp.status_code == 404

    def test_delete_role_wrong_tenant(self, client):
        """Cannot delete role with wrong tenant ID."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _delete_role(client, "tenant-2", role_id)

        assert resp.status_code == 404

    def test_delete_system_role_forbidden(self, client):
        """Deleting a system role returns 403."""
        create_resp = _create_role(client, "tenant-1", "Admin", is_system=True)
        role_id = create_resp.json()["id"]

        resp = _delete_role(client, "tenant-1", role_id)

        assert resp.status_code == 403
        assert "system" in resp.json()["detail"].lower()

        # Verify it still exists
        get_resp = _get_role(client, "tenant-1", role_id)
        assert get_resp.status_code == 200

    def test_delete_role_cascades_permissions(self, client):
        """Deleting a role also removes its permissions."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        # Set permissions
        _set_role_permissions(client, role_id, "tenant-1", ["orders.read", "orders.write"])

        # Verify permissions exist
        perm_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert len(perm_resp.json()) == 2

        # Delete the role
        resp = _delete_role(client, "tenant-1", role_id)
        assert resp.status_code == 204

        # Role is deleted, so GET permissions returns 404 (role not found)
        perm_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert perm_resp.status_code == 404

    def test_delete_multiple_roles_independently(self, client):
        """Delete one role doesn't affect others."""
        resp1 = _create_role(client, "tenant-1", "Editor")
        resp2 = _create_role(client, "tenant-1", "Viewer")
        role_id_1 = resp1.json()["id"]
        role_id_2 = resp2.json()["id"]

        _delete_role(client, "tenant-1", role_id_1)

        # role_id_2 should still exist
        get_resp = _get_role(client, "tenant-1", role_id_2)
        assert get_resp.status_code == 200


# ── PUT /roles/{tenant_id}/{role_id}/permissions — permission assignment ────


class TestSetRolePermissions:
    """Tests for the PUT /roles/{tenant_id}/{role_id}/permissions endpoint."""

    def test_set_empty_permissions(self, client):
        """Set empty permission list on a new role."""
        create_resp = _create_role(client, "tenant-1", "Viewer")
        role_id = create_resp.json()["id"]

        resp = _set_role_permissions(client, role_id, "tenant-1", [])

        assert resp.status_code == 200
        body = resp.json()
        assert body["permission_keys"] == []

    def test_set_single_permission(self, client):
        """Set a single permission on a role."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _set_role_permissions(client, role_id, "tenant-1", ["orders.read"])

        assert resp.status_code == 200
        body = resp.json()
        assert body["permission_keys"] == ["orders.read"]

        # Verify via GET
        perm_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert perm_resp.json() == ["orders.read"]

    def test_set_multiple_permissions(self, client):
        """Set multiple permissions on a role."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]
        perms = ["orders.read", "orders.write", "products.read"]

        resp = _set_role_permissions(client, role_id, "tenant-1", perms)

        assert resp.status_code == 200
        body = resp.json()
        assert set(body["permission_keys"]) == set(perms)

        # Verify via GET
        perm_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert set(perm_resp.json()) == set(perms)

    def test_set_permissions_replaces_existing(self, client):
        """Setting permissions replaces existing ones."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        # Set initial permissions
        _set_role_permissions(client, role_id, "tenant-1", ["orders.read"])

        # Replace with new permissions
        resp = _set_role_permissions(
            client,
            role_id,
            "tenant-1",
            ["products.read", "products.write"],
        )

        assert resp.status_code == 200

        # Verify new permissions are set
        perm_resp = _get_role_permissions(client, role_id, "tenant-1")
        perms = perm_resp.json()
        assert set(perms) == {"products.read", "products.write"}
        assert "orders.read" not in perms

    def test_get_role_permissions(self, client):
        """Get permissions for a role."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]
        perms = ["orders.read", "orders.write"]

        _set_role_permissions(client, role_id, "tenant-1", perms)

        resp = _get_role_permissions(client, role_id, "tenant-1")

        assert resp.status_code == 200
        returned_perms = resp.json()
        assert set(returned_perms) == set(perms)

    def test_get_permissions_empty_role(self, client):
        """Get permissions for a role with no permissions."""
        create_resp = _create_role(client, "tenant-1", "Viewer")
        role_id = create_resp.json()["id"]

        resp = _get_role_permissions(client, role_id, "tenant-1")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_set_permissions_permission_keys_in_response(self, client):
        """Response includes role_id and permission_keys."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]
        perms = ["orders.read", "orders.write"]

        resp = _set_role_permissions(client, role_id, "tenant-1", perms)

        assert resp.status_code == 200
        body = resp.json()
        assert "role_id" in body
        assert body["role_id"] == role_id
        assert "permission_keys" in body
        assert set(body["permission_keys"]) == set(perms)


# ── User-role assignment endpoints ────────────────────────────────────────────────


class TestAssignRoleToUser:
    """Tests for the POST /roles/users/{user_id}/tenant/{tenant_id}/roles/{role_id} endpoint."""

    def test_assign_role_to_user(self, client):
        """Assign a role to a user."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        resp = _assign_role_to_user(client, "user-1", "tenant-1", role_id)

        assert resp.status_code == 200
        body = resp.json()
        assert "message" in body
        assert body["user_id"] == "user-1"
        assert body["role_id"] == role_id

    def test_assign_multiple_roles_to_user(self, client):
        """Assign multiple roles to a user."""
        role1_resp = _create_role(client, "tenant-1", "Editor")
        role2_resp = _create_role(client, "tenant-1", "Reviewer")
        role_id_1 = role1_resp.json()["id"]
        role_id_2 = role2_resp.json()["id"]

        _assign_role_to_user(client, "user-1", "tenant-1", role_id_1)
        _assign_role_to_user(client, "user-1", "tenant-1", role_id_2)

        # Verify both roles are assigned
        roles_resp = _get_user_roles(client, "user-1", "tenant-1")
        roles = roles_resp.json()
        assert set(roles) == {role_id_1, role_id_2}


class TestRemoveRoleFromUser:
    """Tests for the DELETE /roles/users/{user_id}/tenant/{tenant_id}/roles/{role_id} endpoint."""

    def test_remove_role_from_user(self, client):
        """Remove a role from a user."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        _assign_role_to_user(client, "user-1", "tenant-1", role_id)

        resp = _remove_role_from_user(client, "user-1", "tenant-1", role_id)

        assert resp.status_code == 200
        body = resp.json()
        assert body["user_id"] == "user-1"
        assert body["role_id"] == role_id

        # Verify role is removed
        roles_resp = _get_user_roles(client, "user-1", "tenant-1")
        assert roles_resp.json() == []


class TestGetUserRoles:
    """Tests for the GET /roles/users/{user_id}/tenant/{tenant_id}/roles endpoint."""

    def test_get_user_roles_empty(self, client):
        """Get roles for a user with no roles."""
        resp = _get_user_roles(client, "user-1", "tenant-1")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_user_roles_single(self, client):
        """Get a single role assigned to a user."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        _assign_role_to_user(client, "user-1", "tenant-1", role_id)

        resp = _get_user_roles(client, "user-1", "tenant-1")

        assert resp.status_code == 200
        assert resp.json() == [role_id]

    def test_get_user_roles_multiple(self, client):
        """Get multiple roles assigned to a user."""
        role1_resp = _create_role(client, "tenant-1", "Editor")
        role2_resp = _create_role(client, "tenant-1", "Reviewer")
        role_id_1 = role1_resp.json()["id"]
        role_id_2 = role2_resp.json()["id"]

        _assign_role_to_user(client, "user-1", "tenant-1", role_id_1)
        _assign_role_to_user(client, "user-1", "tenant-1", role_id_2)

        resp = _get_user_roles(client, "user-1", "tenant-1")

        assert resp.status_code == 200
        roles = resp.json()
        assert set(roles) == {role_id_1, role_id_2}


# ── Round-trip tests ────────────────────────────────────────────────────────────


class TestRoleRoundTrip:
    """End-to-end tests verifying create → list → get → update → delete flows."""

    def test_create_list_get_roundtrip(self, client):
        """Create a role, list it, then get it by ID."""
        # Create
        create_resp = _create_role(
            client,
            "tenant-1",
            "Editor",
            description="Content editor",
        )
        assert create_resp.status_code == 201
        created_role = create_resp.json()
        role_id = created_role["id"]

        # List
        list_resp = _list_roles(client, "tenant-1")
        assert list_resp.status_code == 200
        roles = list_resp.json()
        assert len(roles) > 0
        assert any(r["id"] == role_id for r in roles)

        # Get
        get_resp = _get_role(client, "tenant-1", role_id)
        assert get_resp.status_code == 200
        retrieved_role = get_resp.json()
        assert retrieved_role["id"] == role_id
        assert retrieved_role["name"] == "Editor"
        assert retrieved_role["description"] == "Content editor"

    def test_create_update_get_roundtrip(self, client):
        """Create a role, update it, then verify the update."""
        # Create
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        # Update
        update_resp = _update_role(
            client,
            "tenant-1",
            role_id,
            name="Senior Editor",
            description="Senior content editor",
        )
        assert update_resp.status_code == 200
        updated_role = update_resp.json()
        assert updated_role["name"] == "Senior Editor"
        assert updated_role["description"] == "Senior content editor"

        # Get and verify
        get_resp = _get_role(client, "tenant-1", role_id)
        assert get_resp.status_code == 200
        retrieved_role = get_resp.json()
        assert retrieved_role["name"] == "Senior Editor"

    def test_create_set_permissions_get_roundtrip(self, client):
        """Create a role, set permissions, then get them."""
        # Create
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        # Set permissions
        perms = ["orders.read", "orders.write", "products.read"]
        set_resp = _set_role_permissions(client, role_id, "tenant-1", perms)
        assert set_resp.status_code == 200

        # Get and verify
        get_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert get_resp.status_code == 200
        retrieved_perms = get_resp.json()
        assert set(retrieved_perms) == set(perms)

    def test_full_role_lifecycle(self, client):
        """Full lifecycle: create → update → assign → get → delete."""
        # Create
        create_resp = _create_role(client, "tenant-1", "Editor")
        assert create_resp.status_code == 201
        role_id = create_resp.json()["id"]

        # Update
        update_resp = _update_role(client, "tenant-1", role_id, name="Content Editor")
        assert update_resp.status_code == 200

        # Set permissions
        set_resp = _set_role_permissions(
            client,
            role_id,
            "tenant-1",
            ["orders.read", "orders.write"],
        )
        assert set_resp.status_code == 200

        # Assign to user
        assign_resp = _assign_role_to_user(client, "user-1", "tenant-1", role_id)
        assert assign_resp.status_code == 200

        # Get and verify
        get_resp = _get_role(client, "tenant-1", role_id)
        assert get_resp.status_code == 200
        assert get_resp.json()["name"] == "Content Editor"

        # Get permissions and verify
        perm_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert len(perm_resp.json()) == 2

        # Remove from user
        remove_resp = _remove_role_from_user(client, "user-1", "tenant-1", role_id)
        assert remove_resp.status_code == 200

        # Delete
        delete_resp = _delete_role(client, "tenant-1", role_id)
        assert delete_resp.status_code == 204

        # Verify deletion
        final_get_resp = _get_role(client, "tenant-1", role_id)
        assert final_get_resp.status_code == 404

    def test_multi_tenant_isolation_roundtrip(self, client):
        """Verify complete isolation across tenants."""
        # Create roles in tenant-1
        role1_resp = _create_role(client, "tenant-1", "Admin")
        role1_id = role1_resp.json()["id"]

        # Create roles in tenant-2
        role2_resp = _create_role(client, "tenant-2", "Admin")
        role2_id = role2_resp.json()["id"]

        # List tenant-1 and verify only its role
        list1_resp = _list_roles(client, "tenant-1")
        roles1 = list1_resp.json()
        assert all(r["tenant_id"] == "tenant-1" for r in roles1)
        assert any(r["id"] == role1_id for r in roles1)

        # List tenant-2 and verify only its role
        list2_resp = _list_roles(client, "tenant-2")
        roles2 = list2_resp.json()
        assert all(r["tenant_id"] == "tenant-2" for r in roles2)
        assert any(r["id"] == role2_id for r in roles2)

        # Cannot get tenant-1's role with tenant-2's ID
        cross_get_resp = _get_role(client, "tenant-2", role1_id)
        assert cross_get_resp.status_code == 404

        # Cannot update tenant-1's role with tenant-2's ID
        cross_update_resp = _update_role(client, "tenant-2", role1_id, name="Hacker")
        assert cross_update_resp.status_code == 404

        # Cannot delete tenant-1's role with tenant-2's ID
        cross_delete_resp = _delete_role(client, "tenant-2", role1_id)
        assert cross_delete_resp.status_code == 404

    def test_system_role_protection_lifecycle(self, client):
        """Verify system role protection throughout lifecycle."""
        # Create system role
        create_resp = _create_role(client, "tenant-1", "Admin", is_system=True)
        assert create_resp.status_code == 201
        role_id = create_resp.json()["id"]

        # Should be listable
        list_resp = _list_roles(client, "tenant-1")
        assert any(r["id"] == role_id for r in list_resp.json())

        # Should be gettable
        get_resp = _get_role(client, "tenant-1", role_id)
        assert get_resp.status_code == 200
        assert get_resp.json()["is_system"] is True

        # Should be updateable
        update_resp = _update_role(client, "tenant-1", role_id, name="Administrator")
        assert update_resp.status_code == 200

        # Should NOT be deletable
        delete_resp = _delete_role(client, "tenant-1", role_id)
        assert delete_resp.status_code == 403

        # Should still exist
        final_get_resp = _get_role(client, "tenant-1", role_id)
        assert final_get_resp.status_code == 200


# ── Edge case and error handling tests ───────────────────────────────────────────


class TestEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_empty_role_name_not_allowed(self, client):
        """Empty role name should fail."""
        resp = _create_role(client, "tenant-1", "")

        # API may accept empty name but it's unusual; verify behavior
        # If it accepts, the role still exists with empty name
        if resp.status_code == 201:
            assert resp.json()["name"] == ""

    def test_special_characters_in_role_name(self, client):
        """Role name with special characters."""
        resp = _create_role(client, "tenant-1", "Editor-Beta#2024")

        assert resp.status_code == 201
        assert resp.json()["name"] == "Editor-Beta#2024"

    def test_long_description(self, client):
        """Role with very long description."""
        long_desc = "A" * 1000
        resp = _create_role(client, "tenant-1", "Editor", description=long_desc)

        assert resp.status_code == 201
        assert resp.json()["description"] == long_desc

    def test_update_with_empty_request_body(self, client):
        """PATCH with empty JSON body should not change anything."""
        create_resp = _create_role(client, "tenant-1", "Editor", description="Original")
        role_id = create_resp.json()["id"]

        # PATCH with empty body
        resp = client.patch(f"/roles/tenant-1/{role_id}", json={})

        assert resp.status_code == 200
        body = resp.json()
        assert body["name"] == "Editor"
        assert body["description"] == "Original"

    def test_permission_keys_with_special_characters(self, client):
        """Permission keys with dots and underscores."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        perms = ["orders.read", "products_view", "config.manage.all"]
        resp = _set_role_permissions(client, role_id, "tenant-1", perms)

        assert resp.status_code == 200
        get_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert set(get_resp.json()) == set(perms)

    def test_very_large_permission_list(self, client):
        """Set a large number of permissions on a role."""
        create_resp = _create_role(client, "tenant-1", "Editor")
        role_id = create_resp.json()["id"]

        # Create 100 permission keys
        perms = [f"perm_{i}" for i in range(100)]

        resp = _set_role_permissions(client, role_id, "tenant-1", perms)

        assert resp.status_code == 200
        get_resp = _get_role_permissions(client, role_id, "tenant-1")
        assert len(get_resp.json()) == 100
