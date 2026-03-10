"""FastAPI router for ClaimMappingConfig CRUD operations.

Provides REST endpoints for managing versioned JWT claim field transformation configs.
Supports creating new versions, retrieving versions, and rolling back to previous versions.
"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Depends, Body, Query

from porth_common.models.claim_mapping_config import ClaimMappingConfig
from porth_common.repositories.claim_mapping_config_repo import (
    ClaimMappingConfigRepository,
)

from ..dependencies import get_claim_mapping_config_repo

router = APIRouter(prefix="/claim-mapping-configs", tags=["claim-mapping-configs"])


@router.post("/", response_model=ClaimMappingConfig)
def create_claim_mapping_config(
    tenant_id: str = Query(...),
    app_namespace: str = Query(...),
    mapping_source: dict = Body(...),
    compiled_ops: list[dict] = Body(...),
    compiled_hash: str = Query(...),
    example_jwt: Optional[dict] = Body(None),
    validation_report: Optional[dict] = Body(None),
    repo: ClaimMappingConfigRepository = Depends(get_claim_mapping_config_repo),
) -> ClaimMappingConfig:
    """Create a new version of the claim mapping config.

    Automatically increments the version number. This endpoint is typically called
    by the claim mapping compiler after transforming human-readable mapping
    configurations into executable operations.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        mapping_source: Human-readable mapping configuration
        compiled_ops: Compiled operations list (execution-ready)
        compiled_hash: SHA256 hash of compiled ops for integrity checking
        example_jwt: Optional example JWT used for validation
        validation_report: Optional validation results
        repo: ClaimMappingConfigRepository (injected)

    Returns:
        Created ClaimMappingConfig entity with auto-incremented version

    Raises:
        HTTPException: 400 if creation fails
    """
    try:
        return repo.save(
            tenant_id=tenant_id,
            app_namespace=app_namespace,
            mapping_source=mapping_source,
            compiled_ops=compiled_ops,
            compiled_hash=compiled_hash,
            example_jwt=example_jwt,
            validation_report=validation_report,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/{app_namespace}/latest", response_model=ClaimMappingConfig)
def get_latest_claim_mapping_config(
    tenant_id: str,
    app_namespace: str,
    repo: ClaimMappingConfigRepository = Depends(get_claim_mapping_config_repo),
) -> ClaimMappingConfig:
    """Get the latest version of the claim mapping config.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        repo: ClaimMappingConfigRepository (injected)

    Returns:
        Latest ClaimMappingConfig entity

    Raises:
        HTTPException: 404 if no config found
    """
    config = repo.get_latest(tenant_id, app_namespace)
    if not config:
        raise HTTPException(status_code=404, detail="Claim mapping config not found")
    return config


@router.get("/{tenant_id}/{app_namespace}/versions", response_model=list[ClaimMappingConfig])
def list_claim_mapping_config_versions(
    tenant_id: str,
    app_namespace: str,
    repo: ClaimMappingConfigRepository = Depends(get_claim_mapping_config_repo),
) -> list[ClaimMappingConfig]:
    """List all versions of the claim mapping config for a tenant and namespace.

    Versions are returned in order of creation (ascending version number).

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        repo: ClaimMappingConfigRepository (injected)

    Returns:
        List of all ClaimMappingConfig versions
    """
    try:
        return repo.list_versions(tenant_id, app_namespace)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{tenant_id}/{app_namespace}/{version}", response_model=ClaimMappingConfig)
def get_claim_mapping_config_version(
    tenant_id: str,
    app_namespace: str,
    version: int,
    repo: ClaimMappingConfigRepository = Depends(get_claim_mapping_config_repo),
) -> ClaimMappingConfig:
    """Get a specific version of the claim mapping config.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        version: Version number
        repo: ClaimMappingConfigRepository (injected)

    Returns:
        ClaimMappingConfig entity for the requested version

    Raises:
        HTTPException: 404 if version not found
    """
    config = repo.get_version(tenant_id, app_namespace, version)
    if not config:
        raise HTTPException(status_code=404, detail="Claim mapping config version not found")
    return config


@router.post("/{tenant_id}/{app_namespace}/rollback/{version}", response_model=ClaimMappingConfig)
def rollback_claim_mapping_config(
    tenant_id: str,
    app_namespace: str,
    version: int,
    repo: ClaimMappingConfigRepository = Depends(get_claim_mapping_config_repo),
) -> ClaimMappingConfig:
    """Rollback to a previous version of the claim mapping config.

    Creates a new version with the configuration from the target version.
    Does not delete the current version, enabling audit trails and easy re-application.

    Args:
        tenant_id: Tenant identifier
        app_namespace: Application namespace
        version: Version number to rollback to
        repo: ClaimMappingConfigRepository (injected)

    Returns:
        New ClaimMappingConfig version created from the rollback

    Raises:
        HTTPException: 404 if target version not found
        HTTPException: 400 if rollback fails
    """
    try:
        return repo.rollback(tenant_id, app_namespace, version)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
