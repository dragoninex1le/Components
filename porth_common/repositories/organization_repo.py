"""DynamoDB repository for Organization entity."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_USERS
from porth_common.events.publisher import EventPublisher
from porth_common.models.organization import Organization
from porth_common.repositories.base import BaseRepository, generate_id, utc_now


class OrganizationRepository(BaseRepository):
    """Repository for managing Organization entities in DynamoDB.

    Uses single-table design with "porth-users" table:
    - PK: ORG#{id}, SK: METADATA
    - GSI1: gsi1pk=ORG_SLUG#{slug}, gsi1sk=METADATA (for slug lookups)
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_USERS,
        dynamodb_resource=None,
        event_publisher: EventPublisher | None = None,
    ):
        super().__init__(table_name, dynamodb_resource)
        self._event_publisher = event_publisher or EventPublisher()

    def create(self, org_data: dict[str, Any]) -> Organization:
        """Create a new organization.

        Args:
            org_data: Dictionary with organization fields (name, slug, etc.)
                     Do not include id, created_at, or updated_at

        Returns:
            Created Organization entity

        Publishes:
            Organization.created event
        """
        org_id = generate_id()
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

        # Publish created event
        self._event_publisher.publish(
            source="porth.user-management",
            detail_type="Organization.created",
            detail=org_data_with_id,
        )

        return Organization(**org_data_with_id)

    def get_by_id(self, org_id: str) -> Organization | None:
        """Retrieve an organization by ID."""
        response = self._table.get_item(
            Key={"PK": f"ORG#{org_id}", "SK": "METADATA"}
        )
        if "Item" not in response:
            return None
        item = response["Item"]
        return Organization(
            id=item["id"],
            name=item["name"],
            slug=item["slug"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    def get_by_slug(self, slug: str) -> Organization | None:
        """Retrieve an organization by slug using GSI1."""
        response = self._table.query(
            IndexName="gsi1",
            KeyConditionExpression=Key("gsi1pk").eq(f"ORG_SLUG#{slug}"),
        )
        if not response["Items"]:
            return None
        item = response["Items"][0]
        return Organization(
            id=item["id"],
            name=item["name"],
            slug=item["slug"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    def list_all(self, limit: int = 100) -> list[Organization]:
        """List all organizations."""
        response = self._table.scan(Limit=limit)
        organizations = []
        for item in response.get("Items", []):
            if "ORG#" in item["PK"]:
                organizations.append(
                    Organization(
                        id=item["id"],
                        name=item["name"],
                        slug=item["slug"],
                        created_at=item["created_at"],
                        updated_at=item["updated_at"],
                    )
                )
        return organizations

    def update(self, org_id: str, updates: dict[str, Any]) -> Organization:
        """Update an organization."""
        updates["updated_at"] = utc_now()

        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates.keys())
        expr_values = {f":{k}": v for k, v in updates.items()}

        response = self._table.update_item(
            Key={"PK": f"ORG#{org_id}", "SK": "METADATA"},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )

        item = response["Attributes"]

        # Publish updated event
        self._event_publisher.publish(
            source="porth.user-management",
            detail_type="Organization.updated",
            detail={k: v for k, v in item.items() if not k.startswith("PK") and not k.startswith("SK") and not k.startswith("gsi")},
        )

        return Organization(
            id=item["id"],
            name=item["name"],
            slug=item["slug"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    def delete(self, org_id: str) -> bool:
        """Delete an organization."""
        try:
            self._table.delete_item(Key={"PK": f"ORG#{org_id}", "SK": "METADATA"})

            # Publish deleted event
            self._event_publisher.publish(
                source="porth.user-management",
                detail_type="Organization.deleted",
                detail={"id": org_id},
            )
            return True
        except Exception:
            return False
