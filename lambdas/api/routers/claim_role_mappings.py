"""FastAPI router for ClaimRoleMapping CRUD operations.

Provides REST endpoints for managing JWT claim-to-role mappings.
These mappings enable automatic role assignment based on identity provider claims.
"""

from fastapi import APIRouter, HTTPException, Depends, Body, Query

from porth_common.models.claim_role_mapping import ClaimRoleMapping
from porth_common.repositories.claim_role_mapping_repo import (
    ClaimRoleMappingRepository,
)

from ..dependencies import get_claim_role_mapping_repo

router = APIRouter(prefix="/claim-role-mappings", tags=["claim-role-mappings"])


@router.post("/", response_model=ClaimRoleMapping)
def create_claim_role_mapping(
    tenant_id: str = Query(...),
    app_namespace: str = Query(...),
    claim_key: str = Query(...),
    claim_value: str = Query(...),
    role_id: str = Query(...),
    priority: int = Query(0),
    repo: ClaimRoleMappingRepository = Depends(get_claim_role_mapping_repo),
) -> ClaimRoleMapping:
    """Create a new claim-to-role mapping.

    Enables mapping of identity provider claims (groups, departments, roles from LDAP,
    Okta, etc.) to internal Porth roles for automatic JIT provisioning.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        claim_key: JWT claim key to match (e.g., 'groups', 'roles')
        claim_value: Expected value in the claim
        role_id: Internal role ID to assign when claim matches
        priority: Priority ordering (higher values evaluated first)
        repo: ClaimRoleMappingRepository (injected)

    Returns:
        Created ClaimRoleMapping entity

    Raises:
        HTTPException: 400 if creation fails
    """
    try:
        return repo.create(
            tenant_id=tenant_id,
            app_namespace=app_namespace,
            claim_key=claim_key,
            claim_value=claim_value,
            role_id=role_id,
            priority=priority,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/{app_namespace}/{mapping_id}", response_model=ClaimRoleMapping)
def get_claim_role_mapping(
    tenant_id: str,
    app_namespace: str,
    mapping_id: str,
    repo: ClaimRoleMappingRepository = Depends(get_claim_role_mapping_repo),
) -> ClaimRoleMapping:
    """Get a claim-to-role mapping by ID.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        mapping_id: Mapping ID
        repo: ClaimRoleMappingRepository (injected)

    Returns:
        ClaimRoleMapping entity

    Raises:
        HTTPException: 404 if mapping not found
    """
    mapping = repo.get_by_id(tenant_id, app_namespace, mapping_id)
    if not mapping:
        raise HTTPException(status_code=404, detail="Claim role mapping not found")
    return mapping


@router.get("/tenant/{tenant_id}", response_model=list[ClaimRoleMapping])
def list_claim_role_mappings_by_tenant(
    tenant_id: str,
    repo: ClaimRoleMappingRepository = Depends(get_claim_role_mapping_repo),
) -> list[ClaimRoleMapping]:
    """List all claim-to-role mappings for a tenant across all namespaces.

    Args:
        tenant_id: Tenant identifier
        repo: ClaimRoleMappingRepository (injected)

    Returns:
        List of all ClaimRoleMapping entities for the tenant
    """
    try:
        return repo.list_by_tenant(tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tenant/{tenant_id}/namespace/{app_namespace}", response_model=list[ClaimRoleMapping])
def list_claim_role_mappings_by_namespace(
    tenant_id: str,
    app_namespace: str,
    repo: ClaimRoleMappingRepository = Depends(get_claim_role_mapping_repo),
) -> list[ClaimRoleMapping]:
    """List all claim-to-role mappings for a specific tenant and namespace.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        repo: ClaimRoleMappingRepository (injected)

    Returns:
        List of ClaimRoleMapping entities for the namespace
    """
    try:
        return repo.list_by_tenant_and_namespace(tenant_id, app_namespace)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{tenant_id}/{app_namespace}/{mapping_id}", response_model=ClaimRoleMapping)
def update_claim_role_mapping(
    tenant_id: str,
    app_namespace: str,
    mapping_id: str,
    data: dict = Body(...),
    repo: ClaimRoleMappingRepository = Depends(get_claim_role_mapping_repo),
) -> ClaimRoleMapping:
    """Update a claim-to-role mapping.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        mapping_id: Mapping ID
        data: Fields to update (claim_key, claim_value, role_id, priority, is_active, etc.)
        repo: ClaimRoleMappingRepository (injected)

    Returns:
        Updated ClaimRoleMapping entity

    Raises:
        HTTPException: 404 if mapping not found
        HTTPException: 400 if update fails
    """
    try:
        mapping = repo.update(tenant_id, app_namespace, mapping_id, data)
        if not mapping:
            raise HTTPException(status_code=404, detail="Claim role mapping not found")
        return mapping
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{tenant_id}/{app_namespace}/{mapping_id}")
def delete_claim_role_mapping(
    tenant_id: str,
    app_namespace: str,
    mapping_id: str,
    repo: ClaimRoleMappingRepository = Depends(get_claim_role_mapping_repo),
) -> dict:
    """Delete a claim-to-role mapping.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        mapping_id: Mapping ID
        repo: ClaimRoleMappingRepository (injected)

    Returns:
        Confirmation message

    Raises:
        HTTPException: 400 if deletion fails
    """
    try:
        repo.delete(tenant_id, app_namespace, mapping_id)
        return {"message": "Claim role mapping deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
