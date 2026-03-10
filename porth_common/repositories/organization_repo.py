"""DynamoDB repository for Organization entity.

Implements Organization persistence in Porth's single-table design. Supports:
- Creating organizations with sequential integer IDs (starting at 1000)
- Slug-based lookups (organizations are frequently accessed by slug in URLs)
- Atomic slug updates via GSI
- Event publishing for downstream consumers

The single-table design stores organizations with:
  - PK: ORG#{id}, SK: METADATA (main access pattern: get by org_id)
  - GSI1: gsi1pk=ORG_SLUG#{slug}, gsi1sk=METADATA (alternate: get by slug for URL routing)
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_USERS
from porth_common.events.publisher import EventPublisher
from porth_common.models.organization import Organization
from porth_common.repositories.base import BaseRepository, generate_sequential_id, utc_now


class OrganizationRepository(BaseRepository):
    """Repository for managing Organization entities in DynamoDB.

    Persistence layer for organizations in Porth's multi-tenant system. Organizations
    are the top-level billing and configuration boundary. This repository handles:
    - Creation with sequential integer IDs (1000, 1001, ...)
    - Slug-based lookups for URL routing
    - Updates with atomic GSI synchronization
    - Event publishing for organization lifecycle changes

    Single-table design with "porth-users" table:
    - PK: ORG#{id}, SK: METADATA (get_by_id access pattern)
    - GSI1: gsi1pk=ORG_SLUG#{slug}, gsi1sk=METADATA (get_by_slug access pattern)

    Note: Organization ID is sequential (not UUID) for human readability in logs,
    queries, and cross-system references. Tenants and Users reference org_id as a string.
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_USERS,
        dynamodb_resource=None,
        event_publisher: EventPublisher | None = None,
    ):
        """Initialize OrganizationRepository.

        Args:
            table_name: DynamoDB table name (default: porth-users)
            dynamodb_resource: Optional boto3 resource for dependency injection
            event_publisher: Optional EventPublisher for domain events
        """
        super().__init__(table_name, dynamodb_resource)
        self._event_publisher = event_publisher or EventPublisher()

    def create(self, org_data: dict[str, Any]) -> Organization:
        """Create a new organization.

        Generates a sequential organization ID (starting at 1000) and publishes
        an Organization.created event. The slug must be globally unique.

        Args:
            org_data: Dictionary with organization fields (name, slug, etc.)
                     Do not include id, created_at, or updated_at

        Returns:
            Created Organization entity

        Publishes:
            Organization.created event with full organization state
        """
        org_id = generate_sequential_id("ORG", self._table)
        now = utc_now()

        org_data_with_id = {
            "id": org_id,
            "created_at": now,
            "updated_at": now,
            **org_data,
        }

        item = {
            "PK": f"ORG#{org_id}",
            "SK": "METADATA",
            "gsi1pk": f"ORG_SLUG#{org_data_with_id['slug']}",
            "gsi1sk": "METADATA",
            **org_data_with_id,
        }

        self._put_item(item)

        org = Organization(**org_data_with_id)

        self._event_publisher.publish(
            entity_type="Organization",
            action="created",
            entity_id=org_id,
            after=org.model_dump(),
            metadata={"organization_id": org_id},
        )

        return org

    def get_by_id(self, org_id: str) -> Organization | None:
        """Get an organization by ID.

        Args:
            org_id: Organization ID (sequential integer, e.g., "1000", "1001")

        Returns:
            Organization if found, None otherwise
        """
        item = self._get_item({"PK": f"ORG#{org_id}", "SK": "METADATA"})
        if not item:
            return None

        # Remove DynamoDB metadata fields
        org_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
        org_data.pop("PK", None)
        org_data.pop("SK", None)

        return Organization(**org_data)

    def get_by_slug(self, slug: str) -> Organization | None:
        """Get an organization by slug.

        Args:
            slug: Organization slug

        Returns:
            Organization if found, None otherwise
        """
        items = self._query_gsi(
            index_name="gsi1",
            key_condition=Key("gsi1pk").eq(f"ORG_SLUG#{slug}")
            & Key("gsi1sk").eq("METADATA"),
        )

        if not items:
            return None

        item = items[0]
        org_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
        org_data.pop("PK", None)
        org_data.pop("SK", None)

        return Organization(**org_data)

    def update(self, org_id: str, updates: dict[str, Any]) -> Organization | None:
        """Update an organization.

        Args:
            org_id: Organization ID (sequential integer)
            updates: Dictionary of fields to update (do not include id, created_at)

        Returns:
            Updated Organization entity, or None if not found

        Publishes:
            Organization.updated event with before/after state
        """
        # Get the current organization first
        current_org = self.get_by_id(org_id)
        if not current_org:
            return None

        # Update the updated_at timestamp
        updates["updated_at"] = utc_now()

        # Handle slug change in GSI
        update_dict = updates.copy()
        if "slug" in updates:
            update_dict["gsi1pk"] = f"ORG_SLUG#{updates['slug']}"

        updated_item = self._update_item(
            {"PK": f"ORG#{org_id}", "SK": "METADATA"},
            update_dict,
        )

        # Remove DynamoDB metadata fields
        org_data = {k: v for k, v in updated_item.items() if not k.startswith("gsi")}
        org_data.pop("PK", None)
        org_data.pop("SK", None)

        org = Organization(**org_data)

        self._event_publisher.publish(
            entity_type="Organization",
            action="updated",
            entity_id=org_id,
            before=current_org.model_dump(),
            after=org.model_dump(),
            metadata={"organization_id": org_id},
        )

        return org

    def list_all(self) -> list[Organization]:
        """List all organizations.

        Returns:
            List of all Organization entities
        """
        # For single-table design, we scan with a filter expression
        from boto3.dynamodb.conditions import Attr

        items = []
        kwargs = {
            "FilterExpression": Attr("PK").begins_with("ORG#"),
        }

        while True:
            response = self._table.scan(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key

        organizations = []
        for item in items:
            org_data = {k: v for k, v in item.items() if not k.startswith("gsi")}
            org_data.pop("PK", None)
            org_data.pop("SK", None)
            organizations.append(Organization(**org_data))

        return organizations
