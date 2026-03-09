"""Pydantic model for Organization entity."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Organization(BaseModel):
    """Organization entity model."""

    id: str = Field(description="Unique organization ID (UUID)")
    name: str = Field(description="Organization name")
    slug: str = Field(description="URL-friendly slug, unique across all organizations")
    status: str = Field(
        default="active",
        description="Organization status",
        pattern="^(active|suspended)$",
    )
    company_details: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional business information (name, registration number, etc.)",
    )
    addresses: Optional[list[dict[str, Any]]] = Field(
        default=None,
        description="Optional list of organization addresses",
    )
    billing_config: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional billing configuration",
    )
    idp_config: Optional[dict[str, Any]] = Field(
        default=None,
        description="Identity Provider configuration at org level (issuer, client_id, audience, jwks_uri)",
    )
    settings: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional organization-level settings",
    )
    created_at: str = Field(description="ISO 8601 datetime when organization was created")
    updated_at: str = Field(description="ISO 8601 datetime when organization was last updated")

    model_config = {"extra": "allow"}
