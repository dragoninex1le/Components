"""FastAPI router for Permission CRUD operations.

Provides REST endpoints for idempotent permission registration and listing.
Permissions are atomic capabilities scoped to applications (namespaces) and tenants.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query

from porth_common.models.permission import Permission
from porth_common.repositories.permission_repo import PermissionRepository

from ..dependencies import get_permission_repo

router = APIRouter(prefix="/permissions", tags=["permissions"])


@router.post("/", response_model=Permission)
def register_permission(
    tenant_id: str = Query(...),
    app_namespace: str = Query(...),
    key: str = Query(...),
    display_name: str = Query(...),
    category: str = Query(...),
    description: Optional[str] = Query(None),
    icon_hint: Optional[str] = Query(None),
    sort_order: int = Query(0),
    repo: PermissionRepository = Depends(get_permission_repo),
) -> Permission:
    """Register a new permission or update an existing one (idempotent).

    On first registration, creates a new permission. On subsequent calls with
    the same tenant_id, app_namespace, and key, updates mutable fields
    (display_name, description, icon_hint, sort_order).

    This endpoint follows the PORTH-10 pattern for idempotent permission registration,
    allowing applications to safely re-register permissions at startup.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        key: Unique permission key (e.g., 'orders.read')
        display_name: Human-readable name
        category: UI grouping category
        description: Optional detailed description
        icon_hint: Optional icon hint for UI
        sort_order: Sort order for UI display
        repo: PermissionRepository (injected)

    Returns:
        Permission entity (created or updated)

    Raises:
        HTTPException: 400 if registration fails
    """
    try:
        return repo.register(
            tenant_id=tenant_id,
            app_namespace=app_namespace,
            key=key,
            display_name=display_name,
            category=category,
            description=description,
            icon_hint=icon_hint,
            sort_order=sort_order,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[Permission])
def list_permissions(
    tenant_id: str = Query(...),
    app_namespace: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    repo: PermissionRepository = Depends(get_permission_repo),
) -> list[Permission]:
    """List permissions with optional filtering.

    Args:
        tenant_id: Tenant identifier (required)
        app_namespace: Optional filter by application namespace
        category: Optional filter by category
        repo: PermissionRepository (injected)

    Returns:
        List of Permission entities

    Raises:
        HTTPException: 400 if query fails
    """
    try:
        all_permissions = repo.list_by_tenant(tenant_id)

        # Apply optional filters
        if app_namespace:
            all_permissions = [
                p for p in all_permissions if p.app_namespace == app_namespace
            ]
        if category:
            all_permissions = [p for p in all_permissions if p.category == category]

        return all_permissions
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/{app_namespace}/{key}", response_model=Permission)
def get_permission(
    tenant_id: str,
    app_namespace: str,
    key: str,
    repo: PermissionRepository = Depends(get_permission_repo),
) -> Permission:
    """Get a specific permission by key.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        key: Permission key
        repo: PermissionRepository (injected)

    Returns:
        Permission entity

    Raises:
        HTTPException: 404 if permission not found
    """
    permission = repo.get_by_key(tenant_id, app_namespace, key)
    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")
    return permission
