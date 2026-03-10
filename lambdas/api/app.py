"""Porth REST API FastAPI application.

A FastAPI application providing CRUD endpoints for all porth-common entities:
- Organizations, Tenants, Users (single-table design with multi-tenant support)
- Permissions (namespace-scoped, tenant-specific)
- Roles, RolePermissions, UserRoles (RBAC system)
- ClaimRoleMappings (claim-based role assignment for SSO)
- ClaimMappingConfigs (versioned claim transformation pipelines)

The application runs as an AWS Lambda function behind API Gateway via the Mangum ASGI adapter.

Entry point for Lambda: handler (async function)
"""

from fastapi import FastAPI
from mangum import Mangum

from .routers import (
    organizations,
    tenants,
    users,
    permissions,
    roles,
    claim_role_mappings,
    claim_mapping_configs,
)

# Create FastAPI application with metadata
app = FastAPI(
    title="Porth User Management API",
    description="REST API for Porth user management, multi-tenancy, RBAC, and claim-based provisioning",
    version="1.0.0",
)

# Include all routers
app.include_router(organizations.router)
app.include_router(tenants.router)
app.include_router(users.router)
app.include_router(permissions.router)
app.include_router(roles.router)
app.include_router(claim_role_mappings.router)
app.include_router(claim_mapping_configs.router)


@app.get("/")
def root() -> dict:
    """Return API information.

    This root endpoint provides basic information about the API,
    useful for health checks and documentation reference.

    Returns:
        Dictionary with API metadata
    """
    return {
        "message": "Porth User Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "openapi_schema": "/openapi.json",
    }


# Mangum handler for AWS Lambda + API Gateway integration
# This wraps the FastAPI ASGI application to handle Lambda events and responses
handler = Mangum(app, lifespan="off")
