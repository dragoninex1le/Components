"""DynamoDB repository for Tenant entity.

Implements Tenant persistence in Porth's single-table design. Supports:
- Creating tenants with sequential integer IDs (starting at 1000)
- Listing tenants by organization
- Atomic updates with event publishing

The single-table design stores tenants with:
  - PK: TENANT#{id}, SK: METADATA (main access pattern: get by tenant_id)
  - GSI1: gsi1pk=ORG#{org_id}, gsi1sk=TENANT#{id} (alternate: list tenants by org)
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_USERS
from porth_common.events.publisher import EventPublisher
from porth_common.models.tenant import Tenant
from porth_common.repositories.base import BaseRepository, generate_sequential_id, utc_now


class TenantRepository(BaseRepository):
    """Repository for managing Tenant entities in DynamoDB.

    Persistence layer for tenants in Porth's multi-tenant system. Tenants are isolated
    environments within organizations where users, roles, and permissions are scoped.
    This repository handles:
    - Creation with sequential integer IDs (1000, 1001, ...)
    - Organization-based listing (query all tenants in an org)
    - Updates with event publishing

    Single-table design with "porth-users" table:
    - PK: TENANT#{id}, SK: METADATA (get_by_id access pattern)
    - GSI1: gsi1pk=ORG#{org_id}, gsi1sk=TENANT#{id} (list_by_org access pattern)

    Note: Tenant ID is sequential (not UUID) for human readability. Tenants belong to
    organizations and are referenced by sequential IDs in users, roles, and permissions.
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_USERS,
        dynamodb_resource=None,
        event_publisher: EventPublisher | None = None,
    ):
        """Initialize TenantRepository.

        Args:
            table_name: DynamoDB table name (default: porth-users)
            dynamodb_resource: Optional boto3 resource for dependency injection
            event_publisher: Optional EventPublisher for domain events
        """
        super().__init__(table_name, dynamodb_resource)
        self._event_publisher = event_publisher or EventPublisher()

    def create(self, tenant_data: dict[str, Any]) -> Tenant:
        """Create a new tenant.

        Generates a sequential tenant ID (starting at 1000) and publishes a
        Tenant.created event. Tenant slug must be unique within the organization.

        Args:
            tenant_data: Dictionary with tenant fields (organization_id, name, slug, etc.)
                        Do not include id, created_at, or updated_at

        Returns:
            Created Tenant entity

        Publishes:
            Tenant.created event with full tenant state
        """
        tenant_id = generate_sequential_id("TENANT", self._table)
        now = utc_now()
        org_id = tenant_data["organization_id"]

        tenant_data_with_id = {
            "id": tenant_id,
            "created_at": now,
            "updated_at": now,
            **tenant_data,
        }

        item = {
            "PK": f"TENANT#{tenant_id}",
            "SK": "METADATA",
            "gsi1pk": f"ORG#{org_id}",
            "gsi1sk": f"TENANT#{tenant_id}",
            **tenant_data_with_id,
        }

        self._put_item(item)

        tenant = Tenant(**tenant_data_with_id)

        self._event_publisher.publish(
            entity_type="Tenant",
            action="created",
            entity_id=tenant_id,
            after=tenant.model_dump(),
            metadata={"organization_id": org_id, "tenant_id": tenant_id},
        )

        return tenant

    def get_by_id(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID.

        Args:
            tenant_id: Tenant ID (sequential integer, e.g., "1000", "1001")

        Returns:
            Tenant if found, None otherwise
        """
        item = self._get_item({"PK": f"TENANT#{tenant_id}", "SK": "METADATA"})
        if not item:
            return None

        # Remove DynamoDB metadata fields
        tenant_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
        tenant_data.pop("PK", None)
        tenant_data.pop("SK", None)

        return Tenant(**tenant_data)

    def list_by_org(self, org_id: str) -> list[Tenant]:
        """List all tenants for an organization.

        Args:
            org_id: Organization ID (sequential integer)

        Returns:
            List of Tenant entities for the organization
        """
        items = self._query_gsi(
            index_name="gsi1",
            key_condition=Key("gsi1pk").eq(f"ORG#{org_id}")
            & Key("gsi1sk").begins_with("TENANT#"),
        )

        tenants = []
        for item in items:
            tenant_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
            tenant_data.pop("PK", None)
            tenant_data.pop("SK", None)
            tenants.append(Tenant(**tenant_data))

        return tenants

    def update(self, tenant_id: str, updates: dict[str, Any]) -> Tenant | None:
        """Update a tenant.

        Args:
            tenant_id: Tenant ID (sequential integer)
            updates: Dictionary of fields to update (do not include id, created_at)

        Returns:
            Updated Tenant entity, or None if not found

        Publishes:
            Tenant.updated event with before/after state
        """
        # Get the current tenant first
        current_tenant = self.get_by_id(tenant_id)
        if not current_tenant:
            return None

        # Update the updated_at timestamp
        updates["updated_at"] = utc_now()

        updated_item = self._update_item(
            {"PK": f"TENANT#{tenant_id}", "SK": "METADATA"},
            updates,
        )

        # Remove DynamoDB metadata fields
        tenant_data = {k: v for k, v in updated_item.items() if not k.startswith("gsi")}
        tenant_data.pop("PK", None)
        tenant_data.pop("SK", None)

        tenant = Tenant(**tenant_data)

        self._event_publisher.publish(
            entity_type="Tenant",
            action="updated",
            entity_id=tenant_id,
            before=current_tenant.model_dump(),
            after=tenant.model_dump(),
            metadata={
                "organization_id": current_tenant.organization_id,
                "tenant_id": tenant_id,
            },
        )

        return tenant
