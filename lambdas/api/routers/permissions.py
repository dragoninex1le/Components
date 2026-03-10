"""FastAPI router for Permission CRUD operations.

Provides REST endpoints for idempotent permission registration and listing.
Permissions are atomic capabilities scoped to applications (namespaces) and tenants.

Implements PORTH-10: Permission registration and listing API.
- POST /permissions — batch-register one or more permissions (idempotent)
- GET /permissions — list permissions with namespace and tenant filtering
- GET /permissions/{tenant_id}/{app_namespace}/{key} — get a specific permission
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from porth_common.models.permission import Permission
from porth_common.repositories.permission_repo import PermissionRepository

from ..dependencies import get_permission_repo

router = APIRouter(prefix="/permissions", tags=["permissions"])


class PermissionRegistrationItem(BaseModel):
    """Single permission to register in a batch request.

    Used by consuming applications at startup to declare their permission model.
    Keys follow the convention '{resource}.{action}' (e.g., 'orders.read').
    """

    key: str = Field(description="Permission key, e.g. 'orders.read'")
    display_name: str = Field(description="Human-readable name")
    category: str = Field(description="UI grouping category, e.g. 'Orders'")
    description: Optional[str] = Field(
        default=None, description="Optional detailed description"
    )
    icon_hint: Optional[str] = Field(
        default=None, description="Optional icon hint for UI"
    )
    sort_order: int = Field(default=0, description="Sort order within category")


class BatchPermissionRequest(BaseModel):
    """Request body for batch permission registration.

    Consuming applications POST this at startup to declare all their permissions.
    Registration is idempotent: re-registering an existing key updates mutable fields only.
    """

    tenant_id: str = Field(description="Tenant identifier")
    app_namespace: str = Field(
        description="Application namespace, e.g. 'cart-agent'"
    )
    permissions: list[PermissionRegistrationItem] = Field(
        description="Permissions to register"
    )


class BatchPermissionResponse(BaseModel):
    """Response from batch permission registration."""

    registered: list[Permission] = Field(
        description="All registered permissions (created or updated)"
    )
    count: int = Field(description="Number of permissions registered")


@router.post("/", response_model=BatchPermissionResponse)
def register_permissions(
    request: BatchPermissionRequest,
    repo: PermissionRepository = Depends(get_permission_repo),
) -> BatchPermissionResponse:
    """Register one or more permissions (idempotent batch operation).

    Used by consuming applications at startup to declare their permission model.
    Each permission is registered individually via PermissionRepository.register(),
    which handles idempotent upserts: new keys are created, existing keys have their
    mutable fields updated (display_name, description, icon_hint, sort_order).

    The namespaced key convention is '{app_namespace}:{key}' at the API level,
    but storage uses app_namespace as a partition key prefix separately.

    Args:
        request: BatchPermissionRequest containing tenant_id, app_namespace,
                 and an array of permissions to register
        repo: PermissionRepository (injected)

    Returns:
        BatchPermissionResponse with all registered permissions

    Raises:
        HTTPException: 400 if any registration fails
    """
    try:
        registered: list[Permission] = []
        for perm in request.permissions:
            result = repo.register(
                tenant_id=request.tenant_id,
                app_namespace=request.app_namespace,
                key=perm.key,
                display_name=perm.display_name,
                category=perm.category,
                description=perm.description,
                icon_hint=perm.icon_hint,
                sort_order=perm.sort_order,
            )
            registered.append(result)
        return BatchPermissionResponse(
            registered=registered, count=len(registered)
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/", response_model=list[Permission])
def list_permissions(
    tenant_id: str = Query(..., description="Tenant identifier (required)"),
    app_namespace: Optional[str] = Query(
        None, description="Filter by application namespace"
    ),
    category: Optional[str] = Query(None, description="Filter by UI category"),
    repo: PermissionRepository = Depends(get_permission_repo),
) -> list[Permission]:
    """List permissions with optional filtering.

    When app_namespace is provided, uses the efficient DynamoDB primary key query
    (list_by_namespace) instead of fetching all tenant permissions via GSI.
    This is the recommended query pattern for consuming applications that only
    need their own permissions.

    Args:
        tenant_id: Tenant identifier (required — all permissions are tenant-scoped)
        app_namespace: Optional filter by application namespace (uses efficient PK query)
        category: Optional filter by UI category (applied client-side)
        repo: PermissionRepository (injected)

    Returns:
        List of Permission entities matching the filters

    Raises:
        HTTPException: 400 if query fails
    """
    try:
        if app_namespace:
            # Efficient: query by primary key (PK = TENANT#...#NS#...)
            permissions = repo.list_by_namespace(tenant_id, app_namespace)
        else:
            # Broader: query by GSI1 (gsi1pk = TENANT#...)
            permissions = repo.list_by_tenant(tenant_id)

        # Apply optional category filter client-side
        if category:
            permissions = [p for p in permissions if p.category == category]

        return permissions
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/{app_namespace}/{key}", response_model=Permission)
def get_permission(
    tenant_id: str,
    app_namespace: str,
    key: str,
    repo: PermissionRepository = Depends(get_permission_repo),
) -> Permission:
    """Get a specific permission by its composite key.

    Looks up a single permission using the DynamoDB primary key
    (PK = TENANT#{tenant_id}#NS#{app_namespace}, SK = PERM#{key}).

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        key: Permission key (e.g., 'orders.read')
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
