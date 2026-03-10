"""Dependency injection for FastAPI routes.

Provides repository instances and DynamoDB table connections for all CRUD operations.
Repositories are instantiated once per request and made available via FastAPI's
dependency injection system.
"""

import os

import boto3
from fastapi import Depends

from porth_common.repositories.claim_mapping_config_repo import (
    ClaimMappingConfigRepository,
)
from porth_common.repositories.claim_role_mapping_repo import (
    ClaimRoleMappingRepository,
)
from porth_common.repositories.organization_repo import OrganizationRepository
from porth_common.repositories.permission_repo import PermissionRepository
from porth_common.repositories.role_repo import RoleRepository
from porth_common.repositories.tenant_repo import TenantRepository
from porth_common.repositories.user_repo import UserRepository
from porth_common.config import (
    TABLE_PORTH_CLAIM_MAPPING_CONFIGS,
    TABLE_PORTH_CLAIM_ROLE_MAPPINGS,
    TABLE_PORTH_PERMISSIONS,
    TABLE_PORTH_ROLES,
    TABLE_PORTH_USERS,
    DYNAMODB_ENDPOINT,
    AWS_REGION,
)


def get_dynamodb_resource():
    """Create and return a boto3 DynamoDB resource.

    Supports both AWS DynamoDB (production) and local DynamoDB
    (testing) based on DYNAMODB_ENDPOINT environment variable.

    Returns:
        boto3 DynamoDB resource configured with the appropriate endpoint
    """
    kwargs = {"region_name": AWS_REGION}
    if DYNAMODB_ENDPOINT:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def get_organization_repo(
    dynamodb_resource=Depends(get_dynamodb_resource),
) -> OrganizationRepository:
    """Dependency to get an OrganizationRepository instance.

    Args:
        dynamodb_resource: DynamoDB resource (injected)

    Returns:
        Initialized OrganizationRepository
    """
    return OrganizationRepository(
        table_name=TABLE_PORTH_USERS, dynamodb_resource=dynamodb_resource
    )


def get_tenant_repo(
    dynamodb_resource=Depends(get_dynamodb_resource),
) -> TenantRepository:
    """Dependency to get a TenantRepository instance.

    Args:
        dynamodb_resource: DynamoDB resource (injected)

    Returns:
        Initialized TenantRepository
    """
    return TenantRepository(
        table_name=TABLE_PORTH_USERS, dynamodb_resource=dynamodb_resource
    )


def get_user_repo(
    dynamodb_resource=Depends(get_dynamodb_resource),
) -> UserRepository:
    """Dependency to get a UserRepository instance.

    Args:
        dynamodb_resource: DynamoDB resource (injected)

    Returns:
        Initialized UserRepository
    """
    return UserRepository(
        table_name=TABLE_PORTH_USERS, dynamodb_resource=dynamodb_resource
    )


def get_permission_repo(
    dynamodb_resource=Depends(get_dynamodb_resource),
) -> PermissionRepository:
    """Dependency to get a PermissionRepository instance.

    Args:
        dynamodb_resource: DynamoDB resource (injected)

    Returns:
        Initialized PermissionRepository
    """
    return PermissionRepository(
        table_name=TABLE_PORTH_PERMISSIONS, dynamodb_resource=dynamodb_resource
    )


def get_role_repo(
    dynamodb_resource=Depends(get_dynamodb_resource),
) -> RoleRepository:
    """Dependency to get a RoleRepository instance.

    Args:
        dynamodb_resource: DynamoDB resource (injected)

    Returns:
        Initialized RoleRepository
    """
    return RoleRepository(
        table_name=TABLE_PORTH_ROLES, dynamodb_resource=dynamodb_resource
    )


def get_claim_role_mapping_repo(
    dynamodb_resource=Depends(get_dynamodb_resource),
) -> ClaimRoleMappingRepository:
    """Dependency to get a ClaimRoleMappingRepository instance.

    Args:
        dynamodb_resource: DynamoDB resource (injected)

    Returns:
        Initialized ClaimRoleMappingRepository
    """
    return ClaimRoleMappingRepository(
        table_name=TABLE_PORTH_CLAIM_ROLE_MAPPINGS,
        dynamodb_resource=dynamodb_resource,
    )


def get_claim_mapping_config_repo(
    dynamodb_resource=Depends(get_dynamodb_resource),
) -> ClaimMappingConfigRepository:
    """Dependency to get a ClaimMappingConfigRepository instance.

    Args:
        dynamodb_resource: DynamoDB resource (injected)

    Returns:
        Initialized ClaimMappingConfigRepository
    """
    return ClaimMappingConfigRepository(
        table_name=TABLE_PORTH_CLAIM_MAPPING_CONFIGS,
        dynamodb_resource=dynamodb_resource,
    )
