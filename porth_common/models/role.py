"""Role, RolePermission, and UserRole entity models for tenant-based access control.

This module defines the RBAC (Role-Based Access Control) structure in Porth. Roles are
tenant-scoped collections of permissions that bridge the gap between atomic permissions
and users. The three classes work together:
- Role: defines a role within a tenant
- RolePermission: join entity linking permissions to roles
- UserRole: join entity linking users to roles

Together they enable flexible, fine-grained access control where users can have multiple
roles and roles can have multiple permissions.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class Role(BaseModel):
    """Role entity for tenant-based access control.

    Why Roles exist:
    - Simplify permission management by grouping permissions into named roles
    - Enable role-based access control (RBAC) instead of per-user permission grants
    - Support role reuse across multiple users
    - Allow fine-grained delegation (e.g., create "Editor", "Reviewer", "Viewer" roles)

    Key relationships:
    - Many-to-one with Tenant (roles are tenant-scoped)
    - Many-to-many with Permission (through RolePermission)
    - Many-to-many with User (through UserRole)

    Business rules:
    - A role is a collection of permissions that can be assigned to users within a tenant
    - System roles (is_system=True) are undeletable and typically represent fixed roles
    - Every tenant gets a system "Admin" role with all permissions during tenant creation
    - Non-system roles are fully customizable and can be deleted
    - Roles are tenant-scoped; the same role name can exist in different tenants independently
    """

    id: str = Field(description="Unique role ID (UUID)")
    tenant_id: str = Field(description="Parent tenant ID (sequential integer, not UUID)")
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
    """Join entity linking permissions to roles within a tenant.

    Why RolePermission exists:
    - Enables many-to-many relationship between roles and permissions
    - Tracks when each permission was added to a role
    - Allows efficient permission lookup for role-based authorization checks

    Key relationships:
    - Points to Role (by role_id) and Permission (by permission_key)
    - Always scoped to a tenant

    Business rules:
    - The combination of role_id + permission_key must be unique within a tenant
    - Permissions are referenced by key (not ID) for better human readability
    - assigned_at tracks audit trail of when permissions were granted
    """

    role_id: str = Field(description="Role ID (UUID)")
    permission_key: str = Field(description="Permission key, e.g. 'orders.read'")
    tenant_id: str = Field(description="Parent tenant ID (sequential integer, not UUID)")
    assigned_at: str = Field(description="ISO 8601 timestamp when permission was assigned to role")

    model_config = {"extra": "allow"}


class UserRole(BaseModel):
    """Join entity linking users to roles within a tenant.

    Why UserRole exists:
    - Enables many-to-many relationship between users and roles
    - Tracks when each role was assigned to a user (audit trail)
    - Allows efficient role lookup for authorization decisions

    Key relationships:
    - Points to User (by user_id), Role (by role_id), and Tenant (by tenant_id)
    - Scoped to a specific tenant

    Business rules:
    - The same user can have different roles in different tenants
    - A user can have multiple roles within a single tenant
    - Roles grant all of their permissions to the user
    - assigned_at timestamp enables audit trails and role history
    - User access = union of all permissions from all assigned roles in the tenant
    """

    user_id: str = Field(description="User ID (UUID)")
    role_id: str = Field(description="Role ID (UUID)")
    tenant_id: str = Field(description="Parent tenant ID (sequential integer, not UUID)")
    assigned_at: str = Field(
        description="ISO 8601 timestamp when role was assigned to user"
    )

    model_config = {"extra": "allow"}
