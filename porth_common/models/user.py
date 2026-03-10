"""User entity model for the Porth multi-tenant user management system.

Users are the leaf tier of Porth's three-level hierarchy: Organization → Tenant → User.
Each user is scoped to a specific tenant and inherits the organization through that tenant.
The same person across different tenants will have separate user records with different IDs.

Users can be provisioned just-in-time (JIT) from JWT claims during login, or manually
created. Their roles and permissions are always tenant-specific, enabling fine-grained
access control within each environment.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class User(BaseModel):
    """User entity model.

    Why Users exist:
    - Represent individuals in the system with identity and profile information
    - Enable role-based access control (RBAC) within a tenant
    - Support just-in-time (JIT) provisioning from identity providers
    - Track user activity and status (active, suspended)

    Key relationships:
    - Many-to-one with Tenant (multiple users per tenant)
    - Many-to-one with Organization (through tenant)
    - Many-to-many with Role (through UserRole join table)

    Business rules:
    - Users are tenant-scoped; same external_id in different tenants = different users
    - external_id + organization_id + tenant_id is a unique upsert key
    - Can be suspended to revoke all access without deletion
    - User email must be unique within a tenant
    - is_org_admin grants broad organization-level privileges (rare)
    - is_billing_contact marks users authorized to view/modify billing

    JIT Provisioning flow:
    - When user logs in with JWT, system creates/updates user based on JWT claims
    - external_id (from IdP) + org_id + tenant_id = upsert key
    - Subsequent logins update user profile fields from JWT
    """

    id: str = Field(description="Unique user ID (UUID)")
    external_id: str = Field(description="User ID from the identity provider (e.g., from JWT 'sub' claim)")
    email: str = Field(description="User email address (unique within tenant)")
    first_name: Optional[str] = Field(
        default=None,
        description="User's first name (from IdP profile)",
    )
    last_name: Optional[str] = Field(
        default=None,
        description="User's last name (from IdP profile)",
    )
    display_name: Optional[str] = Field(
        default=None,
        description="User's display name (derived from IdP claims or manual entry)",
    )
    avatar_url: Optional[str] = Field(
        default=None,
        description="URL to user's avatar image (from IdP or manual)",
    )
    organization_id: str = Field(description="Parent organization ID (sequential integer, not UUID)")
    tenant_id: str = Field(description="Parent tenant ID (sequential integer, not UUID)")
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
