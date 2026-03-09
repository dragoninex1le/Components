"""Pydantic models for Role, RolePermission, and UserRole entities."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Role(BaseModel):
    """Role entity for tenant-based access control.

    A role is a collection of permissions that can be assigned to users within a tenant.
    System roles (is_system=True) are undeletable and typically represent fixed roles
    like 'Admin' that provide full access to all permissions.
    """

    id: str = Field(description="Unique role ID (UUID)")
    tenant_id: str = Field(description="Parent tenant ID (UUID)")
    name: str = Field(description="Role name, e.g. 'Admin', 'Editor', 'Viewer'")
    description: Optional[str] = Field(
        default=None, description="Optional description of the role's purpose"
    )
    is_system: bool = Field(
        default=False,
        description="If True, this is a system role that cannot be deleted",
    )
    created_at: str = Field(description="ISO 8601 creation timestamp")
    updated_at: str = Field(description="ISO 8601 last update timestamp")

    model_config = {"extra": "allow"}


class RolePermission(BaseModel):
    """Represents the assignment of a permission to a role.

    This is a join entity linking roles to permissions within a tenant context.
    """

    role_id: str = Field(description="Role ID (UUID)")
    permission_key: str = Field(description="Permission key, e.g. 'orders.read'")
    tenant_id: str = Field(description="Parent tenant ID (UUID)")
    assigned_at: str = Field(description="ISO 8601 timestamp when permission was assigned")

    model_config = {"extra": "allow"}


class UserRole(BaseModel):
    """Represents the assignment of a role to a user within a tenant.

    This is a join entity linking users to roles. The same user can have
    different roles in different tenants.
    """

    user_id: str = Field(description="User ID (UUID)")
    role_id: str = Field(description="Role ID (UUID)")
    tenant_id: str = Field(description="Parent tenant ID (UUID)")
    assigned_at: str = Field(
        description="ISO 8601 timestamp when role was assigned to user"
    )

    model_config = {"extra": "allow"}
