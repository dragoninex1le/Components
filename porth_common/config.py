"""Porth Common configuration and constants."""

import os

# AWS Configuration
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
DYNAMODB_ENDPOINT = os.environ.get("DYNAMODB_ENDPOINT")  # For local testing

# Table names (overridable via env vars for testing)
TABLE_PORTH_USERS = os.environ.get("PORTH_USERS_TABLE", "porth-users")
TABLE_PORTH_PERMISSIONS = os.environ.get("PORTH_PERMISSIONS_TABLE", "porth-permissions")
TABLE_PORTH_ROLES = os.environ.get("PORTH_ROLES_TABLE", "porth-roles")
TABLE_PORTH_CLAIM_ROLE_MAPPINGS = os.environ.get(
    "PORTH_CLAIM_ROLE_MAPPINGS_TABLE", "porth-claim-role-mappings"
)
TABLE_PORTH_CLAIM_MAPPING_CONFIGS = os.environ.get(
    "PORTH_CLAIM_MAPPING_CONFIGS_TABLE", "porth-claim-mapping-configs"
)

# EventBridge
EVENT_BUS_NAME = os.environ.get("PORTH_EVENT_BUS", "porth-events")
EVENT_SOURCE = "porth.user-management"

# Suspension defaults
DEFAULT_SUSPENSION_THRESHOLD_DAYS = int(
    os.environ.get("PORTH_SUSPENSION_THRESHOLD_DAYS", "90")
)
