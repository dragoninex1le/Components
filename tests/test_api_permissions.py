"""Unit tests for Permission API endpoints (FastAPI handler level).

Tests the POST /permissions (batch registration) and GET /permissions (listing)
endpoints via FastAPI TestClient, exercising the full handler → repository → DynamoDB flow
with mocked AWS services.

Covers PORTH-10 acceptance criteria:
- Consuming app can register permissions with namespaced keys (e.g. "cart:orders.read")
- Registration is idempotent
- Listing filters by app_namespace
- Permissions are tenant-scoped when tenant_id is provided
"""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws
from fastapi.testclient import TestClient

from tests.conftest import create_table


# ── Fixtures ──────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _set_api_env(monkeypatch):
    """Set environment variables required by the API layer."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")
    monkeypatch.setenv("PORTH_PERMISSIONS_TABLE", "porth-permissions")
    monkeypatch.setenv("PORTH_EVENT_BUS", "porth-events")


@pytest.fixture
def _mock_aws():
    """Provide a mocked AWS environment for the entire test."""
    with mock_aws():
        # Create required DynamoDB table
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        create_table(
            dynamodb,
            "porth-permissions",
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


# ── Helper ────────────────────────────────────────────────────────────────────────


def _batch_register(client, tenant_id, app_namespace, permissions):
    """Helper to POST a batch permission registration request."""
    return client.post(
        "/permissions/",
        json={
            "tenant_id": tenant_id,
            "app_namespace": app_namespace,
            "permissions": permissions,
        },
    )


def _make_perm(key, display_name, category, **kwargs):
    """Build a single permission dict for batch registration."""
    item = {
        "key": key,
        "display_name": display_name,
        "category": category,
    }
    item.update(kwargs)
    return item


# ── POST /permissions — batch registration ────────────────────────────────────────


class TestPostPermissions:
    """Tests for the POST /permissions batch registration endpoint."""

    def test_register_single_permission(self, client):
        """Register a single permission and verify the response."""
        resp = _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 1
        assert len(body["registered"]) == 1

        perm = body["registered"][0]
        assert perm["key"] == "orders.read"
        assert perm["display_name"] == "Read Orders"
        assert perm["category"] == "Orders"
        assert perm["tenant_id"] == "tenant-1"
        assert perm["app_namespace"] == "cart-agent"
        assert perm["id"] is not None
        assert perm["created_at"] is not None
        assert perm["updated_at"] is not None

    def test_register_multiple_permissions(self, client):
        """Register a batch of permissions in a single request."""
        perms = [
            _make_perm("orders.read", "Read Orders", "Orders", sort_order=10),
            _make_perm("orders.write", "Write Orders", "Orders", sort_order=20),
            _make_perm("orders.delete", "Delete Orders", "Orders", sort_order=30),
            _make_perm(
                "products.read",
                "Read Products",
                "Products",
                description="View product catalog",
                icon_hint="package",
                sort_order=10,
            ),
        ]

        resp = _batch_register(client, "tenant-1", "cart-agent", perms)

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 4
        assert len(body["registered"]) == 4

        keys = {p["key"] for p in body["registered"]}
        assert keys == {"orders.read", "orders.write", "orders.delete", "products.read"}

    def test_register_idempotent_updates_description(self, client):
        """Re-registering the same key updates mutable fields only."""
        # First registration
        resp1 = _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [
                _make_perm(
                    "orders.read",
                    "Read Orders",
                    "Orders",
                    description="Original description",
                    sort_order=10,
                )
            ],
        )
        assert resp1.status_code == 200
        perm1 = resp1.json()["registered"][0]
        first_id = perm1["id"]
        first_created = perm1["created_at"]

        # Re-register with updated fields
        resp2 = _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [
                _make_perm(
                    "orders.read",
                    "View All Orders",
                    "Orders",
                    description="Updated description",
                    sort_order=20,
                )
            ],
        )
        assert resp2.status_code == 200
        perm2 = resp2.json()["registered"][0]

        # ID and created_at preserved
        assert perm2["id"] == first_id
        assert perm2["created_at"] == first_created
        # Mutable fields updated
        assert perm2["display_name"] == "View All Orders"
        assert perm2["sort_order"] == 20

    def test_register_with_optional_fields(self, client):
        """Register permissions with all optional fields populated."""
        resp = _batch_register(
            client,
            "tenant-1",
            "ops-agent",
            [
                _make_perm(
                    "config.manage",
                    "Manage Configuration",
                    "Configuration",
                    description="Full configuration management access",
                    icon_hint="settings",
                    sort_order=5,
                )
            ],
        )

        assert resp.status_code == 200
        perm = resp.json()["registered"][0]
        assert perm["description"] == "Full configuration management access"
        assert perm["icon_hint"] == "settings"
        assert perm["sort_order"] == 5

    def test_register_without_optional_fields(self, client):
        """Register permissions with only required fields."""
        resp = _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )

        assert resp.status_code == 200
        perm = resp.json()["registered"][0]
        assert perm["description"] is None
        assert perm["icon_hint"] is None
        assert perm["sort_order"] == 0

    def test_register_empty_batch(self, client):
        """Register an empty batch returns empty response."""
        resp = _batch_register(client, "tenant-1", "cart-agent", [])

        assert resp.status_code == 200
        body = resp.json()
        assert body["count"] == 0
        assert body["registered"] == []

    def test_register_same_key_different_namespaces(self, client):
        """Same permission key can exist in different app_namespaces."""
        # Register in cart-agent
        resp1 = _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("users.read", "Read Users", "Users")],
        )
        assert resp1.status_code == 200

        # Register same key in ops-agent
        resp2 = _batch_register(
            client,
            "tenant-1",
            "ops-agent",
            [_make_perm("users.read", "Read Users", "Users")],
        )
        assert resp2.status_code == 200

        # Both should exist independently
        cart_perm = resp1.json()["registered"][0]
        ops_perm = resp2.json()["registered"][0]
        assert cart_perm["id"] != ops_perm["id"]
        assert cart_perm["app_namespace"] == "cart-agent"
        assert ops_perm["app_namespace"] == "ops-agent"

    def test_register_same_key_different_tenants(self, client):
        """Same permission key can exist in different tenants."""
        resp1 = _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )
        resp2 = _batch_register(
            client,
            "tenant-2",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )

        perm1 = resp1.json()["registered"][0]
        perm2 = resp2.json()["registered"][0]
        assert perm1["id"] != perm2["id"]
        assert perm1["tenant_id"] == "tenant-1"
        assert perm2["tenant_id"] == "tenant-2"


# ── GET /permissions — listing and filtering ──────────────────────────────────────


class TestGetPermissions:
    """Tests for the GET /permissions listing endpoint."""

    def _seed_permissions(self, client):
        """Seed the database with a standard set of test permissions."""
        # Cart agent permissions
        _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [
                _make_perm("orders.read", "Read Orders", "Orders", sort_order=10),
                _make_perm("orders.write", "Write Orders", "Orders", sort_order=20),
                _make_perm("products.read", "Read Products", "Products", sort_order=10),
            ],
        )
        # Ops agent permissions
        _batch_register(
            client,
            "tenant-1",
            "ops-agent",
            [
                _make_perm("config.read", "Read Config", "Configuration", sort_order=10),
                _make_perm("config.write", "Write Config", "Configuration", sort_order=20),
            ],
        )
        # Different tenant
        _batch_register(
            client,
            "tenant-2",
            "cart-agent",
            [
                _make_perm("orders.read", "Read Orders", "Orders"),
            ],
        )

    def test_list_all_tenant_permissions(self, client):
        """List all permissions for a tenant without filters."""
        self._seed_permissions(client)

        resp = client.get("/permissions/", params={"tenant_id": "tenant-1"})
        assert resp.status_code == 200
        perms = resp.json()
        assert len(perms) == 5
        tenant_ids = {p["tenant_id"] for p in perms}
        assert tenant_ids == {"tenant-1"}

    def test_list_by_namespace(self, client):
        """Filter permissions by app_namespace uses efficient PK query."""
        self._seed_permissions(client)

        resp = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "app_namespace": "cart-agent"},
        )
        assert resp.status_code == 200
        perms = resp.json()
        assert len(perms) == 3
        keys = {p["key"] for p in perms}
        assert keys == {"orders.read", "orders.write", "products.read"}

    def test_list_by_namespace_ops(self, client):
        """Filter by ops-agent namespace."""
        self._seed_permissions(client)

        resp = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "app_namespace": "ops-agent"},
        )
        assert resp.status_code == 200
        perms = resp.json()
        assert len(perms) == 2
        keys = {p["key"] for p in perms}
        assert keys == {"config.read", "config.write"}

    def test_list_by_category(self, client):
        """Filter permissions by category."""
        self._seed_permissions(client)

        resp = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "category": "Orders"},
        )
        assert resp.status_code == 200
        perms = resp.json()
        assert len(perms) == 2
        assert all(p["category"] == "Orders" for p in perms)

    def test_list_combined_namespace_and_category(self, client):
        """Filter by both app_namespace and category."""
        self._seed_permissions(client)

        resp = client.get(
            "/permissions/",
            params={
                "tenant_id": "tenant-1",
                "app_namespace": "cart-agent",
                "category": "Products",
            },
        )
        assert resp.status_code == 200
        perms = resp.json()
        assert len(perms) == 1
        assert perms[0]["key"] == "products.read"
        assert perms[0]["category"] == "Products"

    def test_list_tenant_isolation(self, client):
        """Permissions from different tenants are isolated."""
        self._seed_permissions(client)

        # tenant-2 should only see its own permissions
        resp = client.get("/permissions/", params={"tenant_id": "tenant-2"})
        assert resp.status_code == 200
        perms = resp.json()
        assert len(perms) == 1
        assert perms[0]["tenant_id"] == "tenant-2"

    def test_list_empty_results(self, client):
        """Listing for a non-existent tenant returns empty list."""
        resp = client.get("/permissions/", params={"tenant_id": "nonexistent"})
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_empty_namespace(self, client):
        """Listing for a non-existent namespace returns empty list."""
        self._seed_permissions(client)

        resp = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "app_namespace": "nonexistent-app"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_requires_tenant_id(self, client):
        """GET /permissions without tenant_id returns 422."""
        resp = client.get("/permissions/")
        assert resp.status_code == 422


# ── GET /permissions/{tenant_id}/{app_namespace}/{key} ────────────────────────


class TestGetPermissionByKey:
    """Tests for the GET /permissions/{tenant_id}/{app_namespace}/{key} endpoint."""

    def test_get_existing_permission(self, client):
        """Retrieve a specific permission by its composite key."""
        _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )

        resp = client.get("/permissions/tenant-1/cart-agent/orders.read")
        assert resp.status_code == 200
        perm = resp.json()
        assert perm["key"] == "orders.read"
        assert perm["tenant_id"] == "tenant-1"
        assert perm["app_namespace"] == "cart-agent"

    def test_get_nonexistent_permission(self, client):
        """Returns 404 for a non-existent permission."""
        resp = client.get("/permissions/tenant-1/cart-agent/nonexistent.perm")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_get_wrong_namespace(self, client):
        """Permission registered in one namespace is not found in another."""
        _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )

        resp = client.get("/permissions/tenant-1/ops-agent/orders.read")
        assert resp.status_code == 404

    def test_get_wrong_tenant(self, client):
        """Permission registered in one tenant is not found in another."""
        _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )

        resp = client.get("/permissions/tenant-2/cart-agent/orders.read")
        assert resp.status_code == 404


# ── Round-trip tests ────────────────────────────────────────────────────────────


class TestPermissionRoundTrip:
    """End-to-end tests verifying POST → GET consistency."""

    def test_register_then_list(self, client):
        """Register permissions then list them back."""
        perms = [
            _make_perm("orders.read", "Read Orders", "Orders"),
            _make_perm("orders.write", "Write Orders", "Orders"),
        ]
        post_resp = _batch_register(client, "tenant-1", "cart-agent", perms)
        assert post_resp.status_code == 200

        get_resp = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "app_namespace": "cart-agent"},
        )
        assert get_resp.status_code == 200
        listed = get_resp.json()
        assert len(listed) == 2

        listed_keys = {p["key"] for p in listed}
        assert listed_keys == {"orders.read", "orders.write"}

    def test_register_then_get_by_key(self, client):
        """Register a permission then retrieve it by key."""
        post_resp = _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [_make_perm("orders.read", "Read Orders", "Orders")],
        )
        registered_id = post_resp.json()["registered"][0]["id"]

        get_resp = client.get("/permissions/tenant-1/cart-agent/orders.read")
        assert get_resp.status_code == 200
        assert get_resp.json()["id"] == registered_id

    def test_idempotent_register_then_list_count_unchanged(self, client):
        """Re-registering the same permission does not create duplicates."""
        perms = [_make_perm("orders.read", "Read Orders", "Orders")]

        # Register twice
        _batch_register(client, "tenant-1", "cart-agent", perms)
        _batch_register(client, "tenant-1", "cart-agent", perms)

        # Count should still be 1
        get_resp = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "app_namespace": "cart-agent"},
        )
        assert len(get_resp.json()) == 1

    def test_multi_app_multi_tenant_scenario(self, client):
        """Complex scenario: multiple apps across multiple tenants."""
        # Tenant 1 — cart-agent
        _batch_register(
            client,
            "tenant-1",
            "cart-agent",
            [
                _make_perm("orders.read", "Read Orders", "Orders", sort_order=10),
                _make_perm("orders.write", "Write Orders", "Orders", sort_order=20),
                _make_perm("products.read", "Read Products", "Products", sort_order=10),
            ],
        )
        # Tenant 1 — ops-agent
        _batch_register(
            client,
            "tenant-1",
            "ops-agent",
            [
                _make_perm("config.read", "Read Config", "Configuration"),
                _make_perm("users.manage", "Manage Users", "User Management"),
            ],
        )
        # Tenant 2 — cart-agent
        _batch_register(
            client,
            "tenant-2",
            "cart-agent",
            [
                _make_perm("orders.read", "Read Orders", "Orders"),
            ],
        )

        # Tenant 1 all: 5 permissions
        t1_all = client.get("/permissions/", params={"tenant_id": "tenant-1"}).json()
        assert len(t1_all) == 5

        # Tenant 1 cart-agent: 3 permissions
        t1_cart = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "app_namespace": "cart-agent"},
        ).json()
        assert len(t1_cart) == 3

        # Tenant 1 ops-agent: 2 permissions
        t1_ops = client.get(
            "/permissions/",
            params={"tenant_id": "tenant-1", "app_namespace": "ops-agent"},
        ).json()
        assert len(t1_ops) == 2

        # Tenant 2: 1 permission
        t2_all = client.get("/permissions/", params={"tenant_id": "tenant-2"}).json()
        assert len(t2_all) == 1
        assert t2_all[0]["tenant_id"] == "tenant-2"
