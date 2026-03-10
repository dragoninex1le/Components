"""FastAPI router for User CRUD operations.

Provides REST endpoints for user management, including JIT provisioning via upsert,
email-based lookups, listing users by organization+tenant, and user suspension/reactivation.
"""

from fastapi import APIRouter, HTTPException, Depends, Body

from porth_common.models.user import User
from porth_common.repositories.user_repo import UserRepository

from ..dependencies import get_user_repo

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/upsert", response_model=User)
def upsert_user(
    external_id: str,
    org_id: str,
    tenant_id: str,
    data: dict = Body(...),
    repo: UserRepository = Depends(get_user_repo),
) -> User:
    """Create or update a user via JIT provisioning (just-in-time).

    Uses external_id + org_id + tenant_id as the composite upsert key.
    The first call creates a new user; subsequent calls update profile fields.
    This is the primary mechanism for identity provider integration.

    Args:
        external_id: User ID from identity provider (e.g., from JWT 'sub' claim)
        org_id: Organization ID (sequential integer)
        tenant_id: Tenant ID (sequential integer)
        data: User data to create/update (must include email)
        repo: UserRepository (injected)

    Returns:
        User entity (newly created or updated)

    Raises:
        HTTPException: 400 if data validation fails
    """
    try:
        user, _ = repo.upsert_by_external_id(external_id, org_id, tenant_id, data)
        return user
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{user_id}", response_model=User)
def get_user(
    user_id: str,
    repo: UserRepository = Depends(get_user_repo),
) -> User:
    """Get a user by ID.

    Args:
        user_id: User ID (UUID)
        repo: UserRepository (injected)

    Returns:
        User entity

    Raises:
        HTTPException: 404 if user not found
    """
    user = repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/email/{email}/tenant/{tenant_id}", response_model=User)
def get_user_by_email_and_tenant(
    email: str,
    tenant_id: str,
    repo: UserRepository = Depends(get_user_repo),
) -> User:
    """Get a user by email within a specific tenant.

    Args:
        email: User email address
        tenant_id: Tenant ID (sequential integer)
        repo: UserRepository (injected)

    Returns:
        User entity

    Raises:
        HTTPException: 404 if user not found
    """
    user = repo.get_by_email_and_tenant(email, tenant_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/organization/{org_id}/tenant/{tenant_id}", response_model=list[User])
def list_users_by_organization_and_tenant(
    org_id: str,
    tenant_id: str,
    repo: UserRepository = Depends(get_user_repo),
) -> list[User]:
    """List all users for an organization and tenant.

    Args:
        org_id: Organization ID (sequential integer)
        tenant_id: Tenant ID (sequential integer)
        repo: UserRepository (injected)

    Returns:
        List of User entities
    """
    try:
        return repo.list_by_org_and_tenant(org_id, tenant_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{user_id}", response_model=User)
def update_user(
    user_id: str,
    data: dict = Body(...),
    repo: UserRepository = Depends(get_user_repo),
) -> User:
    """Update a user.

    Args:
        user_id: User ID (UUID)
        data: Fields to update
        repo: UserRepository (injected)

    Returns:
        Updated User entity

    Raises:
        HTTPException: 404 if user not found
        HTTPException: 400 if update fails
    """
    try:
        user = repo.update(user_id, data)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/suspend", response_model=User)
def suspend_user(
    user_id: str,
    repo: UserRepository = Depends(get_user_repo),
) -> User:
    """Suspend a user.

    Sets user status to 'suspended' and records the suspension timestamp.

    Args:
        user_id: User ID (UUID)
        repo: UserRepository (injected)

    Returns:
        Updated User entity with suspended status

    Raises:
        HTTPException: 404 if user not found
    """
    try:
        user = repo.suspend(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{user_id}/reactivate", response_model=User)
def reactivate_user(
    user_id: str,
    repo: UserRepository = Depends(get_user_repo),
) -> User:
    """Reactivate a suspended user.

    Sets user status back to 'active' and clears the suspension timestamp.

    Args:
        user_id: User ID (UUID)
        repo: UserRepository (injected)

    Returns:
        Updated User entity with active status

    Raises:
        HTTPException: 404 if user not found
    """
    try:
        user = repo.reactivate(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
