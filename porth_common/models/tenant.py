"""Pydantic model for Tenant entity."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Tenant(BaseModel):
    """Tenant entity model."""

    id: str = Field(description="Unique tenant ID (UUID)")
    organization_id: str = Field(description="Parent organization ID (UUID)")
    name: str = Field(description="Tenant name")
    slug: str = Field(description="URL-friendly slug, unique within organization")
    environment_type: str = Field(
        description="Environment type for this tenant",
        pattern="^(production|staging|development|sandbox)$",
    )
    status: str = Field(
        default="active",
        description="Tenant status",
        pattern="^(active|suspended|provisioning)$",
    )
    settings: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional tenant-level settings",
    )
    feature_flags: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional feature flags for this tenant",
    )
    idp_config_override: Optional[dict[str, Any]] = Field(
        default=None,
        description="Per-tenant Identity Provider configuration override (issuer, client_id, audience). Falls back to organization-level if not set.",
    )
    created_at: str = Field(description="ISO 8601 datetime when tenant was created")
    updated_at: str = Field(description="ISO 8601 datetime when tenant was last updated")

    model_config = {"extra": "allow"}
