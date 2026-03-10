"""FastAPI router for Role CRUD operations and RBAC management.

Provides REST endpoints for role management, permission assignment to roles,
and user-role assignment within tenants.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Body, Query

from porth_common.models.role import Role
from porth_common.repositories.role_repo import RoleRepository

from ..dependencies import get_role_repo

router = APIRouter(prefix="/roles", tags=["roles"])


@router.post("/", response_model=Role)
def create_role(
    tenant_id: str = Query(...),
    name: str = Query(...),
    description: Optional[str] = Query(None),
    is_system: bool = Query(False),
    repo: RoleRepository = Depends(get_role_repo),
) -> Role:
    """Create a new role.

    This endpoint follows the PORTH-11 pattern for role creation,
    enabling tenants to define custom roles for their access control.

    Args:
        tenant_id: Tenant identifier
        name: Role name
        description: Optional role description
        is_system: If True, role cannot be deleted (system role)
        repo: RoleRepository (injected)

    Returns:
        Created Role entity

    Raises:
        HTTPException: 400 if creation fails
    """
    try:
        return repo.create_role(
            tenant_id=tenant_id,
            name=name,
            description=description,
            is_system=is_system,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tenant/{tenant_id}", response_model=list[Role])
def list_roles_by_tenant(
    tenant_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> list[Role]:
    """List all roles for a tenant.

    Args:
        tenant_id: Tenant identifier
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
    """Get a role by ID.

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier
        repo: RoleRepository (injected)

    Returns:
        Role entity

    Raises:
        HTTPException: 404 if role not found
    """
    role = repo.get_role(tenant_id, role_id)
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


@router.patch("/{tenant_id}/{role_id}", response_model=Role)
def update_role(
    tenant_id: str,
    role_id: str,
    name: str = Body(...),
    description: Optional[str] = Body(None),
    repo: RoleRepository = Depends(get_role_repo),
) -> Role:
    """Update a role's name and description.

    The is_system flag cannot be changed via this endpoint.

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier
        name: New role name
        description: New role description
        repo: RoleRepository (injected)

    Returns:
        Updated Role entity

    Raises:
        HTTPException: 404 if role not found
        HTTPException: 400 if update fails
    """
    try:
        return repo.update_role(tenant_id, role_id, name, description)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tenant_id}/{role_id}")
def delete_role(
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> dict:
    """Delete a role and cascade-delete associated role permissions.

    Cannot delete system roles (is_system=True).

    Args:
        tenant_id: Tenant identifier
        role_id: Role identifier
        repo: RoleRepository (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 400 if role is a system role
        HTTPException: 404 if role not found
    """
    try:
        repo.delete_role(tenant_id, role_id)
        return {"message": "Role deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{role_id}/permissions")
def set_role_permissions(
    role_id: str,
    tenant_id: str = Query(...),
    permission_keys: list[str] = Body(...),
    repo: RoleRepository = Depends(get_role_repo),
) -> dict:
    """Set all permissions for a role (replaces existing permissions).

    This is a replacement operation: any permissions not in the provided list
    are removed from the role.

    Args:
        role_id: Role identifier
        tenant_id: Tenant identifier
        permission_keys: List of permission keys to assign
        repo: RoleRepository (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 400 if operation fails
    """
    try:
        repo.set_role_permissions(role_id, permission_keys, tenant_id)
        return {"message": "Role permissions updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{role_id}/permissions", response_model=list[str])
def get_role_permissions(
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> list[str]:
    """List all permission keys for a role.

    Args:
        role_id: Role identifier
        repo: RoleRepository (injected)

    Returns:
        List of permission keys assigned to the role
    """
    try:
        return repo.get_role_permissions(role_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/users/{user_id}/tenant/{tenant_id}/roles/{role_id}")
def assign_role_to_user(
    user_id: str,
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> dict:
    """Assign a role to a user in a tenant.

    Args:
        user_id: User identifier
        tenant_id: Tenant identifier
        role_id: Role identifier
        repo: RoleRepository (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 400 if assignment fails
    """
    try:
        repo.assign_user_role(user_id, role_id, tenant_id)
        return {"message": "Role assigned to user successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}/tenant/{tenant_id}/roles/{role_id}")
def remove_role_from_user(
    user_id: str,
    tenant_id: str,
    role_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> dict:
    """Remove a role from a user in a tenant.

    Args:
        user_id: User identifier
        tenant_id: Tenant identifier
        role_id: Role identifier
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
        return {"message": "Role removed from user successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/users/{user_id}/tenant/{tenant_id}/roles", response_model=list[str])
def get_user_roles(
    user_id: str,
    tenant_id: str,
    repo: RoleRepository = Depends(get_role_repo),
) -> list[str]:
    """List all role IDs assigned to a user in a tenant.

    Args:
        user_id: User identifier
        tenant_id: Tenant identifier
        repo: RoleRepository (injected)

    Returns:
        List of role IDs assigned to the user
    """
    try:
        return repo.get_user_roles(user_id, tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
