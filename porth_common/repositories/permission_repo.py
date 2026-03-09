"""DynamoDB repository for Permission entities."""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_PERMISSIONS
from porth_common.events.publisher import EventPublisher
from porth_common.models.permission import Permission
from porth_common.repositories.base import BaseRepository, generate_id, utc_now


class PermissionRepository(BaseRepository):
    """Repository for managing Permission entities in DynamoDB.

    Table structure:
    - PK: TENANT#{tenant_id}#NS#{app_namespace}
    - SK: PERM#{id}
    - GSI1: gsi1pk=TENANT#{tenant_id}, gsi1sk=PERM#{id}
    - GSI2: gsi2pk=CATEGORY#{category}, gsi2sk=PERM#{id}
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_PERMISSIONS,
        dynamodb_resource=None,
        events_client=None,
    ):
        """Initialize the repository.

        Args:
            table_name: DynamoDB table name
            dynamodb_resource: Optional mocked DynamoDB resource for testing
            events_client: Optional mocked EventBridge client for testing
        """
        super().__init__(table_name, dynamodb_resource)
        self._publisher = EventPublisher(client=events_client)

    def create(
        self,
        tenant_id: str,
        app_namespace: str,
        name: str,
        description: str = "",
        category: str = "default",
    ) -> Permission:
        """Create a new permission.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            name: Permission name (e.g., 'users:read', 'users:write')
            description: Human-readable description
            category: Category for grouping permissions

        Returns:
            Created Permission entity
        """
        perm_id = generate_id()
        now = utc_now()

        item = {
            "PK": f"TENANT#{tenant_id}#NS#{app_namespace}",
            "SK": f"PERM#{perm_id}",
            "gsi1pk": f"TENANT#{tenant_id}",
            "gsi1sk": f"PERM#{perm_id}",
            "gsi2pk": f"CATEGORY#{category}",
            "gsi2sk": f"PERM#{perm_id}",
            "id": perm_id,
            "name": name,
            "description": description,
            "category": category,
            "created_at": now,
            "updated_at": now,
        }

        self._put_item(item)

        # Publish created event
        self._publisher.publish(
            source="porth.user-management",
            detail_type="Permission.created",
            detail={
                "id": perm_id,
                "tenant_id": tenant_id,
                "app_namespace": app_namespace,
                "name": name,
                "category": category,
            },
        )

        return Permission(
            id=perm_id,
            name=name,
            description=description,
            category=category,
            created_at=now,
            updated_at=now,
        )

    def get_by_id(
        self,
        tenant_id: str,
        app_namespace: str,
        perm_id: str,
    ) -> Permission | None:
        """Retrieve a permission by ID."""
        response = self._table.get_item(
            Key={
                "PK": f"TENANT#{tenant_id}#NS#{app_namespace}",
                "SK": f"PERM#{perm_id}",
            }
        )
        if "Item" not in response:
            return None
        return self._item_to_permission(response["Item"])

    def list_by_tenant(
        self,
        tenant_id: str,
        app_namespace: str,
        limit: int = 100,
    ) -> list[Permission]:
        """List all permissions for a tenant."""
        response = self._table.query(
            KeyConditionExpression=Key("PK").eq(
                f"TENANT#{tenant_id}#NS#{app_namespace}"
            )
            & Key("SK").begins_with("PERM#"),
            Limit=limit,
        )
        return [self._item_to_permission(item) for item in response.get("Items", [])]

    def list_by_category(
        self,
        category: str,
        limit: int = 100,
    ) -> list[Permission]:
        """List all permissions in a category using GSI2."""
        response = self._table.query(
            IndexName="gsi2",
            KeyConditionExpression=Key("gsi2pk").eq(f"CATEGORY#{category}"),
            Limit=limit,
        )
        return [self._item_to_permission(item) for item in response.get("Items", [])]

    def update(
        self,
        tenant_id: str,
        app_namespace: str,
        perm_id: str,
        updates: dict[str, Any],
    ) -> Permission | None:
        """Update a permission."""
        updates["updated_at"] = utc_now()

        update_expr = "SET " + ", ".join(f"{k} = :{k}" for k in updates.keys())
        expr_values = {f":{k}": v for k, v in updates.items()}

        response = self._table.update_item(
            Key={
                "PK": f"TENANT#{tenant_id}#NS#{app_namespace}",
                "SK": f"PERM#{perm_id}",
            },
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )

        if "Attributes" not in response:
            return None

        # Publish updated event
        self._publisher.publish(
            source="porth.user-management",
            detail_type="Permission.updated",
            detail={"id": perm_id, "tenant_id": tenant_id},
        )

        return self._item_to_permission(response["Attributes"])

    def delete(
        self,
        tenant_id: str,
        app_namespace: str,
        perm_id: str,
    ) -> bool:
        """Delete a permission."""
        try:
            self._table.delete_item(
                Key={
                    "PK": f"TENANT#{tenant_id}#NS#{app_namespace}",
                    "SK": f"PERM#{perm_id}",
                }
            )

            # Publish deleted event
            self._publisher.publish(
                source="porth.user-management",
                detail_type="Permission.deleted",
                detail={"id": perm_id, "tenant_id": tenant_id},
            )
            return True
        except Exception:
            return False

    def _item_to_permission(self, item: dict[str, Any]) -> Permission:
        """Convert a DynamoDB item to a Permission object."""
        return Permission(
            id=item["id"],
            name=item["name"],
            description=item.get("description", ""),
            category=item.get("category", "default"),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
