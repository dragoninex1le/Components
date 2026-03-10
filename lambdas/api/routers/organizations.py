"""FastAPI router for Organization CRUD operations.

Provides REST endpoints for creating, listing, reading, and updating organizations.
Organizations are the top-level hierarchy in Porth's multi-tenant system.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Body

from porth_common.models.organization import Organization
from porth_common.repositories.organization_repo import OrganizationRepository

from ..dependencies import get_organization_repo

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.post("/", response_model=Organization)
def create_organization(
    data: dict = Body(...),
    repo: OrganizationRepository = Depends(get_organization_repo),
) -> Organization:
    """Create a new organization.

    Args:
        data: Organization data (name, slug, etc.)
        repo: OrganizationRepository (injected)

    Returns:
        Created Organization entity

    Raises:
        HTTPException: 400 if data validation fails
    """
    try:
        return repo.create(data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[Organization])
def list_organizations(
    repo: OrganizationRepository = Depends(get_organization_repo),
) -> list[Organization]:
    """List all organizations.

    Note: This endpoint performs a full table scan and is intended for
    admin use only. In production, consider adding pagination or filtering.

    Args:
        repo: OrganizationRepository (injected)

    Returns:
        List of all Organization entities
    """
    try:
        return repo.list_all()
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{org_id}", response_model=Organization)
def get_organization(
    org_id: str,
    repo: OrganizationRepository = Depends(get_organization_repo),
) -> Organization:
    """Get an organization by ID.

    Args:
        org_id: Organization ID (sequential integer)
        repo: OrganizationRepository (injected)

    Returns:
        Organization entity

    Raises:
        HTTPException: 404 if organization not found
    """
    org = repo.get_by_id(org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.get("/slug/{slug}", response_model=Organization)
def get_organization_by_slug(
    slug: str,
    repo: OrganizationRepository = Depends(get_organization_repo),
) -> Organization:
    """Get an organization by slug.

    Args:
        slug: Organization slug
        repo: OrganizationRepository (injected)

    Returns:
        Organization entity

    Raises:
        HTTPException: 404 if organization not found
    """
    org = repo.get_by_slug(slug)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


@router.patch("/{org_id}", response_model=Organization)
def update_organization(
    org_id: str,
    data: dict = Body(...),
    repo: OrganizationRepository = Depends(get_organization_repo),
) -> Organization:
    """Update an organization.

    Args:
        org_id: Organization ID (sequential integer)
        data: Fields to update
        repo: OrganizationRepository (injected)

    Returns:
        Updated Organization entity

    Raises:
        HTTPException: 404 if organization not found
        HTTPException: 400 if update fails
    """
    try:
        org = repo.update(org_id, data)
        if not org:
            raise HTTPException(status_code=404, detail="Organization not found")
        return org
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
