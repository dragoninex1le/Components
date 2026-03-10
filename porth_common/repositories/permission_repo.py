"""DynamoDB repository for Permission entities.

Implements Permission persistence for multi-application, multi-tenant authorization.
Supports idempotent permission registration (applications define permissions at startup),
grouping by category for UI display, and efficient lookups by namespace and key.

The single-table design stores permissions with:
  - PK: TENANT#{tenant_id}#NS#{app_namespace}, SK: PERM#{key} (main access pattern)
  - GSI1: gsi1pk=TENANT#{tenant_id}, gsi1sk=CAT#{category}#PERM#{key} (category browsing)
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_PERMISSIONS
from porth_common.events.publisher import EventPublisher
from porth_common.models.permission import Permission
from porth_common.repositories.base import BaseRepository, generate_id, utc_now


class PermissionRepository(BaseRepository):
    """Repository for managing permissions in DynamoDB.

    Persistence layer for permissions in Porth's fine-grained access control system.
    Permissions are atomic capabilities registered by applications. This repository handles:
    - Idempotent registration (re-register updates mutable fields only)
    - Namespace-scoped permission sets (different apps, different permissions)
    - Category-based grouping for UI display
    - Efficient lookups by key or category

    Single-table design with "porth-permissions" table:
    - Main: PK: TENANT#{tenant_id}#NS#{app_namespace}, SK: PERM#{key}
    - GSI1: gsi1pk=TENANT#{tenant_id}, gsi1sk=CAT#{category}#PERM#{key} (for UI grouping)

    Note: Permissions are application-scoped via app_namespace. The same permission
    key can exist independently in different namespaces within the same tenant.
    """

    def __init__(self, table_name: str = TABLE_PORTH_PERMISSIONS, dynamodb_resource=None, events_client=None):
        """Initialize the repository.

        Args:
            table_name: DynamoDB table name
            dynamodb_resource: Optional mocked DynamoDB resource for testing
            events_client: Optional mocked EventBridge client for testing
        """
        super().__init__(table_name, dynamodb_resource)
        self._publisher = EventPublisher(client=events_client)

    def register(
        self,
        tenant_id: str,
        app_namespace: str,
        key: str,
        display_name: str,
        category: str,
        description: str | None = None,
        icon_hint: str | None = None,
        sort_order: int = 0,
    ) -> Permission:
        """Register a new permission or update an existing one (idempotent).

        On first registration, creates a new permission. On subsequent calls with
        the same tenant_id, app_namespace, and key, updates mutable fields
        (display_name, description, icon_hint, sort_order).

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            key: Unique permission key (e.g., 'orders.read')
            display_name: Human-readable name
            category: UI grouping category
            description: Optional detailed description
            icon_hint: Optional icon hint for UI
            sort_order: Sort order for UI display

        Returns:
            Permission: The created or updated permission entity
        """
        # Try to get existing permission
        existing = self.get_by_key(tenant_id, app_namespace, key)

        if existing:
            # Idempotent update: update mutable fields
            now = utc_now()
            updates = {
                "display_name": display_name,
                "sort_order": sort_order,
                "updated_at": now,
            }
            if description is not None:
                updates["description"] = description
            if icon_hint is not None:
                updates["icon_hint"] = icon_hint

            pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
            sk_value = f"PERM#{key}"

            updated_item = self._update_item(
                {"pk": pk_value, "sk": sk_value},
                updates,
            )

            # Publish update event
            self._publisher.publish(
                entity_type="Permission",
                action="updated",
                entity_id=existing.id,
                after=updated_item,
                before=existing.model_dump(),
                metadata={"tenant_id": tenant_id, "app_namespace": app_namespace},
            )

            return self._item_to_permission(updated_item)
        else:
            # Create new permission
            permission_id = generate_id()
            now = utc_now()

            pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
            sk_value = f"PERM#{key}"
            gsi1pk_value = f"TENANT#{tenant_id}"
            gsi1sk_value = f"CAT#{category}#PERM#{key}"

            item: dict[str, Any] = {
                "pk": pk_value,
                "sk": sk_value,
                "gsi1pk": gsi1pk_value,
                "gsi1sk": gsi1sk_value,
                "id": permission_id,
                "key": key,
                "display_name": display_name,
                "category": category,
                "app_namespace": app_namespace,
                "tenant_id": tenant_id,
                "sort_order": sort_order,
                "created_at": now,
                "updated_at": now,
            }

            if description is not None:
                item["description"] = description
            if icon_hint is not None:
                item["icon_hint"] = icon_hint

            stored_item = self._put_item(item)

            # Publish create event
            self._publisher.publish(
                entity_type="Permission",
                action="created",
                entity_id=permission_id,
                after=stored_item,
                metadata={"tenant_id": tenant_id, "app_namespace": app_namespace},
            )

            return self._item_to_permission(stored_item)

    def get_by_key(
        self, tenant_id: str, app_namespace: str, key: str
    ) -> Permission | None:
        """Get a permission by its key.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            key: Permission key

        Returns:
            Permission if found, None otherwise
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
        sk_value = f"PERM#{key}"

        item = self._get_item({"pk": pk_value, "sk": sk_value})
        return self._item_to_permission(item) if item else None

    def list_by_tenant(self, tenant_id: str) -> list[Permission]:
        """List all permissions for a tenant (flat list).

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of all permissions for the tenant
        """
        # Query all namespaces by using GSI1
        items = self._query_gsi(
            index_name="gsi1",
            key_condition=Key("gsi1pk").eq(f"TENANT#{tenant_id}"),
        )
        return [self._item_to_permission(item) for item in items if item]

    def list_grouped_by_category(self, tenant_id: str) -> dict[str, list[Permission]]:
        """List permissions grouped by category.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Dictionary mapping category names to lists of permissions
        """
        items = self._query_gsi(
            index_name="gsi1",
            key_condition=Key("gsi1pk").eq(f"TENANT#{tenant_id}"),
        )

        grouped: dict[str, list[Permission]] = {}
        for item in items:
            if item:
                permission = self._item_to_permission(item)
                category = permission.category
                if category not in grouped:
                    grouped[category] = []
                grouped[category].append(permission)

        # Sort permissions within each category by sort_order
        for category in grouped:
            grouped[category].sort(key=lambda p: p.sort_order)

        return grouped

    def list_by_namespace(
        self, tenant_id: str, app_namespace: str
    ) -> list[Permission]:
        """List all permissions for a specific namespace.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace

        Returns:
            List of permissions in the namespace
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"

        items = self._query(
            key_condition=Key("pk").eq(pk_value),
        )
        return [self._item_to_permission(item) for item in items if item]

    @staticmethod
    def _item_to_permission(item: dict[str, Any] | None) -> Permission | None:
        """Convert a DynamoDB item to a Permission model.

        Args:
            item: DynamoDB item dictionary

        Returns:
            Permission model or None if item is None
        """
        if not item:
            return None

        return Permission(
            id=item["id"],
            key=item["key"],
            display_name=item["display_name"],
            description=item.get("description"),
            app_namespace=item["app_namespace"],
            tenant_id=item["tenant_id"],
            category=item["category"],
            icon_hint=item.get("icon_hint"),
            sort_order=item.get("sort_order", 0),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
