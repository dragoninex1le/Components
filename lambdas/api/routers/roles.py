"""FastAPI router for Role CRUD operations and RBAC management.

Provides REST endpoints for tenant-scoped role management, permission assignment
to roles, and user-role assignment. Implements PORTH-11: Role CRUD API.

Endpoints:
- GET /roles — list roles for a tenant
- POST /roles — create a new role
- GET /roles/{tenant_id}/{role_id} — get a role by ID
- PATCH /roles/{tenant_id}/{role_id} — update role name/description
- DELETE /roles/{tenant_id}/{role_id} — delete a role (cascade cleanup)
- PUT /roles/{tenant_id}/{role_id}/permissions — set permissions for a role (replace)
- GET /roles/{tenant_id}/{role_id}/permissions — list permissions for a role
- POST /roles/users/{user_id}/tenant/{tenant_id}/roles/{role_id} — assign role
- DELETE /roles/users/{user_id}/tenant/{tenant_id}/roles/{role_id} — unassign role
- GET /roles/users/{user_id}/tenant/{tenant_id}/roles — list user's roles
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Body, Query
from pydantic import BaseModel, Field

from porth_common.models.role import Role
from porth_common.repositories.role_repo import RoleRepository

from ..dependencies import get_role_repo

router = APIRouter(prefix="/roles", tags=["roles"])


# ── Request/Response models ───────────────────────────────────────────────────────


class CreateRoleRequest(BaseModel):
    """Request body for creating a new role.

    Roles are tenant-scoped containers for permissions. Tenants can define
    custom roles (e.g., 'Editor', 'Viewer') and system roles (e.g., 'Admin')
    that cannot be deleted.
    """

    tenant_id: str = Field(description="Tenant identifier")
    name: str = Field(description="Role name, must be unique within tenant")
    description: Optional[str] = Field(
        default=None, description="Optional role description"
    )
    is_system: bool = Field(
        default=False,
        description="If True, role cannot be deleted (system role)",
    )


class UpdateRoleRequest(BaseModel):
    """Request body for partial role update.

    Only provided fields are updated; omitted fields remain unchanged.
    """

    name: Optional[str] = Field(
        default=None, description="New role name (must be unique within tenant)"
    )
    description: Optional[str] = Field(
        default=None, description="New role description"
    )


# ── CRUD endpoints ──────────────────────────────────────────────────────────────


@router.post("/", response_model=Role, status_code=201)
def create_role(
    request: CreateRoleRequest,
    repo: RoleRepository = Depends(get_role_repo),
) -> Role:
    """Create a new tenant-scoped role.

    Role names must be unique within a tenant. Set is_system=True for
    roles that should be protected from deletion (e.g., system admin role).

    Args:
        request: CreateRoleRequest with tenant_id, name, description, is_system
        repo: RoleRepository (injected)

    Returns:
        Created Role entity (201)

    Raises:
        HTTPException: 400 if creation fails (e.g., duplicate name)
    """
    try:
        return repo.create_role(
            tenant_id=request.tenant_id,
            name=request.name,
            description=request.description,
            is_system=request.is_system,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[Role])
def list_roles(
    tenant_id: str = Query(..., description="Tenant identifier (required)"),
    repo: RoleRepository = Depends(get_role_repo),
) -> list[Role]:
    """List all roles for a tenant.

    Roles are scoped to a tenant — this endpoint only returns roles
    belonging to the specified tenant_id.

    Args:
        tenant_id: Tenant identifier (required)
        repo: RoleRepository (injected)

    Returns:
        List of Role entities for the tenant
    """
    try:
        return repo.list_roles(tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/{role_id}", response_model=Role)
def get_role(
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> Role:
    """Get a specific role by its composite key.

    Enforces tenant scoping: the role must belong to the specified tenant.

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier (UUID)
        repo: RoleRepository (injected)

    Returns:
        Role entity

    Raises:
        HTTPException: 404 if role not found in the specified tenant
    """
    role = repo.get_role(tenant_id, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.patch("/{tenant_id}/{role_id}", response_model=Role)
def update_role(
    tenant_id: str,
    role_id: str,
    request: UpdateRoleRequest,
    repo: RoleRepository = Depends(get_role_repo),
) -> Role:
    """Update a role's name and/or description.

    Partial update: only fields provided in the request body are changed.
    The is_system flag cannot be changed via this endpoint.

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier (UUID)
        request: UpdateRoleRequest with optional name and description
        repo: RoleRepository (injected)

    Returns:
        Updated Role entity

    Raises:
        HTTPException: 404 if role not found
        HTTPException: 400 if update fails (e.g., duplicate name)
    """
    # Verify role exists first
    existing = repo.get_role(tenant_id, role_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")

    # Use existing values for fields not provided in the update
    new_name = request.name if request.name is not None else existing.name
    new_description = (
        request.description if request.description is not None else existing.description
    )

    try:
        return repo.update_role(tenant_id, role_id, new_name, new_description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tenant_id}/{role_id}", status_code=204)
def delete_role(
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
):
    """Delete a role with cascade cleanup.

    Deletes the role and removes all associated role-permission entries.
    System roles (is_system=True) cannot be deleted and return 403.

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier (UUID)
        repo: RoleRepository (injected)

    Returns:
        204 No Content on success

    Raises:
        HTTPException: 403 if attempting to delete a system role
        HTTPException: 404 if role not found
    """
    # Verify role exists
    existing = repo.get_role(tenant_id, role_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")

    try:
        repo.delete_role(tenant_id, role_id)
    except ValueError as e:
        # System role protection
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Permission assignment ─────────────────────────────────────────────────────────


@router.put("/{tenant_id}/{role_id}/permissions")
def set_role_permissions(
    tenant_id: str,
    role_id: str,
    permission_keys: list[str] = Body(...),
    repo: RoleRepository = Depends(get_role_repo),
) -> dict:
    """Set all permissions for a role (full replacement).

    This is a replacement operation: the provided permission_keys become
    the complete permission set for the role. Any previously assigned
    permissions not in the new list are removed.

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier (UUID)
        permission_keys: List of permission keys to assign (replaces existing set)
        repo: RoleRepository (injected)

    Returns:
        Confirmation with the new permission set

    Raises:
        HTTPException: 404 if role not found
        HTTPException: 400 if operation fails
    """
    existing = repo.get_role(tenant_id, role_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")

    try:
        repo.set_role_permissions(role_id, permission_keys, tenant_id)
        return {
            "message": "Role permissions updated",
            "role_id": role_id,
            "permission_keys": permission_keys,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/{role_id}/permissions", response_model=list[str])
def get_role_permissions(
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> list[str]:
    """List all permission keys assigned to a role.

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier (UUID)
        repo: RoleRepository (injected)

    Returns:
        List of permission keys assigned to the role

    Raises:
        HTTPException: 404 if role not found
    """
    existing = repo.get_role(tenant_id, role_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Role not found")

    try:
        return repo.get_role_permissions(role_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── User-role assignment ──────────────────────────────────────────────────────────


@router.post("/users/{user_id}/tenant/{tenant_id}/roles/{role_id}")
def assign_role_to_user(
    user_id: str,
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> dict:
    """Assign a role to a user within a tenant.

    Creates a user-role association. A user can have multiple roles
    within a tenant.

    Args:
        user_id: User identifier
        tenant_id: Tenant identifier
        role_id: Role identifier (UUID)
        repo: RoleRepository (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 400 if assignment fails
    """
    try:
        repo.assign_user_role(user_id, role_id, tenant_id)
        return {"message": "Role assigned to user", "user_id": user_id, "role_id": role_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}/tenant/{tenant_id}/roles/{role_id}")
def remove_role_from_user(
    user_id: str,
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> dict:
    """Remove a role from a user within a tenant.

    Deletes the user-role association. Does not delete the role itself.

    Args:
        user_id: User identifier
        tenant_id: Tenant identifier
        role_id: Role identifier (UUID)
        repo: RoleRepository (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 400 if removal fails
    """
    try:
        pk_value = f"USER#{user_id}#TENANT#{tenant_id}"
        sk_value = f"ROLE#{role_id}"
        repo._delete_item({"pk": pk_value, "sk": sk_value})
        return {"message": "Role removed from user", "user_id": user_id, "role_id": role_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{user_id}/tenant/{tenant_id}/roles", response_model=list[str])
def get_user_roles(
    user_id: str,
    tenant_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> list[str]:
    """List all role IDs assigned to a user within a tenant.

    Args:
        user_id: User identifier
        tenant_id: Tenant identifier
        repo: RoleRepository (injected)

    Returns:
        List of role IDs assigned to the user in the specified tenant
    """
    try:
        return repo.get_user_roles(user_id, tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
