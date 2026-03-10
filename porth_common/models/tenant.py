"""Tenant entity model for the Porth multi-tenant user management system.

A Tenant represents an isolated environment within an Organization. It forms the middle
tier of Porth's three-level hierarchy: Organization → Tenant → User. All users, roles,
and permissions are scoped to a specific tenant.

Tenants enable organizations to run separate environments (production, staging, development)
or isolate different business units/divisions with independent role and permission models,
while maintaining centralized organization-level configuration and billing.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Tenant(BaseModel):
    """Tenant entity model.

    Why Tenants exist:
    - Provide isolated environments within an organization (prod, staging, dev)
    - Enable independent role/permission models per environment
    - Allow different IdP configurations per tenant (override org default)
    - Scope users and access control to specific environments

    Key relationships:
    - Many-to-one with Organization (multiple tenants per org)
    - One-to-many with User (a tenant has multiple users)
    - One-to-many with Role (roles are scoped to tenants)

    Business rules:
    - Slug must be unique within the organization (not globally)
    - Can be provisioning, active, or suspended
    - Inherits organization's IdP config unless it sets its own override
    - Cannot exist without a parent organization
    """

    id: str = Field(description="Unique tenant ID — sequential integer starting at 1000, human-friendly for use in queries, logs, and cross-system references")
    organization_id: str = Field(description="Parent organization ID (sequential integer, not UUID)")
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
