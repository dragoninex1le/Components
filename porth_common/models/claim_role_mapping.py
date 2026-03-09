"""ClaimRoleMapping model for JWT claim to role mapping."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ClaimRoleMapping(BaseModel):
    """Represents a mapping from a JWT claim value to an internal role.

    This model defines how JWT claims (e.g., groups, roles, department) are
    evaluated to determine which internal roles a user should be assigned.
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
