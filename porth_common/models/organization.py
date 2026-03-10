"""Organization entity model for the Porth multi-tenant user management system.

An Organization represents the top-level account in Porth's two-tier multi-tenancy
hierarchy (Organization → Tenant → User). Each organization maps to a single paying
customer and contains one or more tenants representing isolated environments.

Organizations own the default IdP configuration that tenants inherit unless they
provide their own override. This allows a single SSO setup to cover all tenants
while still supporting per-tenant IdP customization for complex enterprise deployments.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class Organization(BaseModel):
    """Organization entity model.

    Why Organizations exist:
    - Represent customer accounts and billing boundaries
    - Centralize configuration (IdP, settings) shared across tenants
    - Enable hierarchical multi-tenancy: Organization → multiple Tenants → Users
    - Allow organization-level admins to manage multiple tenant environments

    Key relationships:
    - One-to-many with Tenant (an org has multiple tenants)
    - Implicit relationship with User through Tenant

    Business rules:
    - Slug must be unique across all organizations (used in URLs)
    - Can be suspended to disable all activity in the organization and its tenants
    - Default IdP config applies to all tenants unless overridden
    """

    id: str = Field(description="Unique organization ID — sequential integer starting at 1000, human-friendly for use in queries, logs, and cross-system references")
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
