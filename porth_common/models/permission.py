"""Permission entity model for Porth's fine-grained access control system.

Permissions represent atomic capabilities in the system. They are registered by applications
at startup (idempotent registration) and become assignable to roles. The permission model
supports multi-tenancy and application namespacing, allowing different applications to
define their own permission models within shared tenants.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Permission(BaseModel):
    """Represents a permission entity with category metadata for UI grouping.

    Why Permissions exist:
    - Represent atomic, specific capabilities in the system
    - Enable fine-grained access control when combined with roles
    - Support multi-application deployments with isolated permission models
    - Enable UI grouping via categories (Orders, Products, Settings, etc.)

    Key relationships:
    - Many-to-many with Role (through RolePermission)
    - Scoped to both Tenant and application namespace (app_namespace)

    Business rules:
    - Permission key must be unique within a tenant/namespace (e.g., 'orders.read')
    - Permissions are application-scoped (different apps have different permission sets)
    - Permissions are registered by applications (typically at startup)
    - Registration is idempotent: re-registering updates mutable fields only
    - Category is UI metadata, not a hierarchy (for grouping in permission selection UIs)
    - Multiple applications can exist in a single tenant with independent permissions
    - sort_order controls display order within a category in the UI
    """

    id: str = Field(description="Unique identifier (UUID)")
    key: str = Field(description="Unique key within tenant/namespace like 'orders.read' or 'products.write'")
    display_name: str = Field(description="Human-readable name for UI display")
    description: str | None = Field(
        default=None, description="Optional detailed description"
    )
    app_namespace: str = Field(
        description="Application namespace, e.g. 'cart-agent', 'ops-agent'"
    )
    tenant_id: str = Field(description="Tenant identifier")
    category: str = Field(
        description="UI grouping context, e.g. 'Orders', 'Products', 'Configuration'"
    )
    icon_hint: str | None = Field(
        default=None, description="Optional icon hint for UI rendering"
    )
    sort_order: int = Field(
        default=0, description="Sort order for UI display within category"
    )
    created_at: str = Field(description="ISO 8601 creation timestamp")
    updated_at: str = Field(description="ISO 8601 last update timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "key": "orders.read",
                "display_name": "Read Orders",
                "description": "View order information",
                "app_namespace": "cart-agent",
                "tenant_id": "tenant-123",
                "category": "Orders",
                "icon_hint": "eye",
                "sort_order": 10,
                "created_at": "2026-03-09T10:00:00+00:00",
                "updated_at": "2026-03-09T10:00:00+00:00",
            }
        }
    )
