"""FastAPI router for Tenant CRUD operations.

Provides REST endpoints for creating, listing, reading, and updating tenants.
Tenants are isolated environments within organizations.
"""

from fastapi import APIRouter, HTTPException, Depends, Body

from porth_common.models.tenant import Tenant
from porth_common.repositories.tenant_repo import TenantRepository

from ..dependencies import get_tenant_repo

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("/", response_model=Tenant)
def create_tenant(
    data: dict = Body(...),
    repo: TenantRepository = Depends(get_tenant_repo),
) -> Tenant:
    """Create a new tenant.

    Args:
        data: Tenant data (organization_id, name, slug, etc.)
        repo: TenantRepository (injected)

    Returns:
        Created Tenant entity

    Raises:
        HTTPException: 400 if data validation fails
    """
    try:
        return repo.create(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}", response_model=Tenant)
def get_tenant(
    tenant_id: str,
    repo: TenantRepository = Depends(get_tenant_repo),
) -> Tenant:
    """Get a tenant by ID.

    Args:
        tenant_id: Tenant ID (sequential integer)
        repo: TenantRepository (injected)

    Returns:
        Tenant entity

    Raises:
        HTTPException: 404 if tenant not found
    """
    tenant = repo.get_by_id(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.get("/organization/{org_id}", response_model=list[Tenant])
def list_tenants_by_organization(
    org_id: str,
    repo: TenantRepository = Depends(get_tenant_repo),
) -> list[Tenant]:
    """List all tenants for an organization.

    Args:
        org_id: Organization ID (sequential integer)
        repo: TenantRepository (injected)

    Returns:
        List of Tenant entities in the organization
    """
    try:
        return repo.list_by_org(org_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{tenant_id}", response_model=Tenant)
def update_tenant(
    tenant_id: str,
    data: dict = Body(...),
    repo: TenantRepository = Depends(get_tenant_repo),
) -> Tenant:
    """Update a tenant.

    Args:
        tenant_id: Tenant ID (sequential integer)
        data: Fields to update
        repo: TenantRepository (injected)

    Returns:
        Updated Tenant entity

    Raises:
        HTTPException: 404 if tenant not found
        HTTPException: 400 if update fails
    """
    try:
        tenant = repo.update(tenant_id, data)
        if not tenant:
            raise HTTPException(status_code=404, detail="Tenant not found")
        return tenant
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
