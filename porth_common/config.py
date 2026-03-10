"""Porth Common configuration and constants.

Centralizes all configuration values for the Porth user management system, including
AWS/DynamoDB settings, table names, event configuration, and business logic defaults.

All values are environment-variable driven for easy deployment configuration across
dev, staging, and production environments.
"""

import os

# ============================================================================
# AWS Configuration
# ============================================================================
# Credentials and region are typically set via AWS SDK environment variables
# (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN, AWS_REGION).
# These can be overridden for local testing or multi-region deployments.

AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
"""AWS region for DynamoDB and EventBridge. Defaults to us-east-1."""

DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")
"""Local DynamoDB endpoint for testing (e.g., http://localhost:8000).
   If not set, connects to AWS DynamoDB in the configured region."""

# ============================================================================
# DynamoDB Table Names
# ============================================================================
# All table names are overridable via environment variables for test isolation
# and multi-environment deployments. Uses descriptive names for clarity.

TABLE_PORTH_USERS = os.environ.get("PORTH_USERS_TABLE", "porth-users")
"""Single-table design for Organizations, Tenants, and Users.
   Contains: ORG, TENANT, USER, and related GSI entries."""

TABLE_PORTH_PERMISSIONS = os.environ.get("PORTH_PERMISSIONS_TABLE", "porth-permissions")
"""Permissions registry by tenant and application namespace.
   Shared across all tenants; application-scoped via namespace."""

TABLE_PORTH_ROLES = os.environ.get("PORTH_ROLES_TABLE", "porth-roles")
"""Roles, role-permission assignments, and user-role assignments.
   Supports tenant-scoped RBAC with permission inheritance."""

TABLE_PORTH_CLAIM_ROLE_MAPPINGS = os.environ.get(
    "PORTH_CLAIM_ROLE_MAPPINGS_TABLE", "porth-claim-role-mappings"
)
"""JWT claim-to-role mappings for automatic role assignment during login.
   Enables enterprise SSO with IdP group mapping."""

TABLE_PORTH_CLAIM_MAPPING_CONFIGS = os.environ.get(
    "PORTH_CLAIM_MAPPING_CONFIGS_TABLE", "porth-claim-mapping-configs"
)
"""Versioned JWT claim transformation configurations.
   Supports rollback and audit trail of configuration changes."""

# ============================================================================
# EventBridge Configuration
# ============================================================================
# All CRUD operations publish domain events to EventBridge for downstream
# consumers (analytics, audit logs, data replication, workflow triggers, etc.)

EVENT_BUS_NAME = os.environ.get("PORTH_EVENT_BUS", "porth-events")
"""EventBridge event bus name for domain events.
   Defaults to 'porth-events'; override for custom event bus."""

EVENT_SOURCE = "porth.user-management"
"""Source identifier for all events published by Porth.
   Used by EventBridge rules and consumers for filtering/routing."""

# ============================================================================
# Business Logic Defaults
# ============================================================================
# These constants define system behavior for suspension, retention, and
# other business rules. All are overridable via environment variables.

DEFAULT_SUSPENSION_THRESHOLD_DAYS = int(
    os.environ.get("PORTH_SUSPENSION_THRESHOLD_DAYS", "90")
)
"""Days of inactivity before automatic suspension (default: 90 days).
   Used by background jobs to suspend inactive users. Set to 0 to disable."""
