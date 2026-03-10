"""ClaimRoleMapping entity model for JWT claim-based role assignment.

ClaimRoleMapping entities define rules for automatically assigning internal roles
based on JWT claim values. They enable organizations to map IdP groups (e.g., LDAP groups,
Okta groups) directly to Porth roles without manual user provisioning, supporting
enterprise SSO flows where group membership drives authorization.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClaimRoleMapping(BaseModel):
    """Represents a mapping from a JWT claim value to an internal role.

    Why ClaimRoleMapping exists:
    - Enable automatic role assignment based on JWT claim values (groups, departments, etc.)
    - Support enterprise SSO flows where IdP groups map to application roles
    - Reduce manual provisioning by deriving roles from identity provider data
    - Allow flexible, priority-based matching (first match wins, or aggregate all matches)

    Key relationships:
    - Many-to-one with Tenant (mappings are tenant-scoped)
    - Many-to-one with application namespace (app_namespace)
    - Points to internal Role by role_id

    Business rules:
    - A mapping defines: if JWT has claim_key with claim_value, assign role_id
    - For list claims (e.g., "groups": ["admin", "users"]), check if claim_value is in list
    - For scalar claims, check if claim_value equals the claim value
    - priority controls evaluation order (higher priority checked first)
    - is_active allows disabling mappings without deletion
    - Multiple mappings can match for a single user (aggregate all matching roles)
    - Used during JIT (just-in-time) provisioning to auto-assign roles on login
    """

    id: str = Field(description="Unique identifier (UUID)")
    tenant_id: str = Field(description="Tenant identifier")
    app_namespace: str = Field(
        description="Application namespace, e.g. 'cart-agent', 'ops-agent'"
    )
    claim_key: str = Field(
        description="JWT claim key to match against, e.g. 'groups', 'roles', 'department'"
    )
    claim_value: str = Field(
        description="Expected value in the claim"
    )
    role_id: str = Field(description="Internal role ID to assign when matched")
    priority: int = Field(
        default=0,
        description="Priority ordering (higher values checked first)",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this mapping is active",
    )
    created_at: str = Field(description="ISO 8601 creation timestamp")
    updated_at: str = Field(description="ISO 8601 last update timestamp")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "tenant_id": "tenant-123",
                "app_namespace": "cart-agent",
                "claim_key": "groups",
                "claim_value": "admin",
                "role_id": "role-admin",
                "priority": 10,
                "is_active": True,
                "created_at": "2026-03-09T10:00:00+00:00",
                "updated_at": "2026-03-09T10:00:00+00:00",
            }
        }
    )
