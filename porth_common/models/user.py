"""Pydantic model for User entity."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """User entity model.

    Users are per-tenant. The same person across different tenants will have
    separate user records with different IDs.
    """

    id: str = Field(description="Unique user ID (UUID)")
    external_id: str = Field(description="User ID from the identity provider")
    email: str = Field(description="User email address")
    first_name: Optional[str] = Field(
        default=None,
        description="User's first name",
    )
    last_name: Optional[str] = Field(
        default=None,
        description="User's last name",
    )
    display_name: Optional[str] = Field(
        default=None,
        description="User's display name",
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="URL to user's avatar image",
    )
    organization_id: str = Field(description="Parent organization ID (UUID)")
    tenant_id: str = Field(description="Parent tenant ID (UUID)")
    status: str = Field(
        default="active",
        description="User status",
        pattern="^(active|suspended)$",
    )
    profile_data: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional user profile data from IdP",
    )
    preferences: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional user preferences - only user-editable field",
    )
    is_org_admin: bool = Field(
        default=False,
        description="Whether user is an organization administrator",
    )
    is_billing_contact: bool = Field(
        default=False,
        description="Whether user is a billing contact for the organization",
    )
    last_login_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 datetime of last login",
    )
    suspended_at: Optional[str] = Field(
        default=None,
        description="ISO 8601 datetime when user was suspended (nullable)",
    )
    created_at: str = Field(description="ISO 8601 datetime when user was created")
    updated_at: str = Field(description="ISO 8601 datetime when user was last updated")

    model_config = {"extra": "allow"}
