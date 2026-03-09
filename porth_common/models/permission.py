"""Permission model for Porth user management system."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Permission(BaseModel):
    """Represents a permission entity with category metadata for UI grouping.

    A permission is an atomic capability within an application namespace.
    The category field is metadata for UI organization—it's not a hierarchical
    classification but rather a context label for grouping related permissions.
    """

    id: str = Field(description="Unique identifier (UUID)")
    key: str = Field(description="Unique key like 'orders.read' or 'products.write'")
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
