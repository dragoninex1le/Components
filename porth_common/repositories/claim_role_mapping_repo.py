"""DynamoDB repository for ClaimRoleMapping entities.

Implements claim-to-role mapping persistence for automatic role assignment based on
JWT claim values. Supports creation, listing, updating, and deletion of mappings
with priority-based evaluation and active/inactive toggling.

The single-table design stores mappings with:
  - PK: TENANT#{tenant_id}#NS#{app_namespace}, SK: MAPPING#{id}
  - GSI1: gsi1pk=TENANT#{tenant_id}, gsi1sk=MAPPING#{id} (listing by tenant)
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_CLAIM_ROLE_MAPPINGS
from porth_common.events.publisher import EventPublisher
from porth_common.models.claim_role_mapping import ClaimRoleMapping
from porth_common.repositories.base import BaseRepository, generate_id, utc_now


class ClaimRoleMappingRepository(BaseRepository):
    """Repository for managing claim-to-role mappings in DynamoDB.

    Persistence layer for JWT claim-based role assignment. Enables mapping of identity
    provider claims (groups, departments, roles from LDAP, Okta, etc.) to internal
    Porth roles for automatic JIT provisioning.

    Single-table design with "porth-claim-role-mappings" table:
    - Main: PK: TENANT#{tenant_id}#NS#{app_namespace}, SK: MAPPING#{id}
    - Listing: GSI1 gsi1pk=TENANT#{tenant_id}, gsi1sk=MAPPING#{id}

    Features:
    - Priority ordering (higher values evaluated first)
    - Active/inactive toggle without deletion
    - Application-namespaced (different apps, different mappings)
    - Event publishing for audit trails
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_CLAIM_ROLE_MAPPINGS,
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
        claim_key: str,
        claim_value: str,
        role_id: str,
        priority: int = 0,
    ) -> ClaimRoleMapping:
        """Create a new claim-to-role mapping.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            claim_key: JWT claim key to match (e.g., 'groups', 'roles')
            claim_value: Expected value in the claim
            role_id: Internal role ID to assign
            priority: Priority ordering (higher first)

        Returns:
            ClaimRoleMapping: The created mapping entity
        """
        mapping_id = generate_id()
        now = utc_now()

        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
        sk_value = f"MAPPING#{mapping_id}"
        gsi1pk_value = f"TENANT#{tenant_id}"
        gsi1sk_value = f"MAPPING#{mapping_id}"

        item: dict[str, Any] = {
            "pk": pk_value,
            "sk": sk_value,
            "gsi1pk": gsi1pk_value,
            "gsi1sk": gsi1sk_value,
            "id": mapping_id,
            "tenant_id": tenant_id,
            "app_namespace": app_namespace,
            "claim_key": claim_key,
            "claim_value": claim_value,
            "role_id": role_id,
            "priority": priority,
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        }

        stored_item = self._put_item(item)

        # Publish create event
        self._publisher.publish(
            entity_type="ClaimRoleMapping",
            action="created",
            entity_id=mapping_id,
            after=stored_item,
            metadata={"tenant_id": tenant_id, "app_namespace": app_namespace},
        )

        return self._item_to_mapping(stored_item)

    def get_by_id(
        self, tenant_id: str, app_namespace: str, mapping_id: str
    ) -> ClaimRoleMapping | None:
        """Get a mapping by its ID.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            mapping_id: Mapping ID

        Returns:
            ClaimRoleMapping if found, None otherwise
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
        sk_value = f"MAPPING#{mapping_id}"

        item = self._get_item({"pk": pk_value, "sk": sk_value})
        return self._item_to_mapping(item) if item else None

    def list_by_tenant(self, tenant_id: str) -> list[ClaimRoleMapping]:
        """List all mappings for a tenant across all namespaces.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of all mappings for the tenant
        """
        items = self._query_gsi(
            index_name="gsi1",
            key_condition=Key("gsi1pk").eq(f"TENANT#{tenant_id}"),
        )
        return [self._item_to_mapping(item) for item in items if item]

    def list_by_tenant_and_namespace(
        self, tenant_id: str, app_namespace: str
    ) -> list[ClaimRoleMapping]:
        """List all mappings for a specific tenant and namespace.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace

        Returns:
            List of mappings for the tenant and namespace
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"

        items = self._query(
            key_condition=Key("pk").eq(pk_value),
        )
        return [self._item_to_mapping(item) for item in items if item]

    def update(
        self,
        tenant_id: str,
        app_namespace: str,
        mapping_id: str,
        updates: dict[str, Any],
    ) -> ClaimRoleMapping:
        """Update a mapping with the given updates.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            mapping_id: Mapping ID
            updates: Dictionary of fields to update

        Returns:
            ClaimRoleMapping: The updated mapping entity
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
        sk_value = f"MAPPING#{mapping_id}"

        # Add updated_at timestamp
        updates["updated_at"] = utc_now()

        # Get the item before update
        existing = self._get_item({"pk": pk_value, "sk": sk_value})

        updated_item = self._update_item(
            {"pk": pk_value, "sk": sk_value},
            updates,
        )

        # Publish update event
        self._publisher.publish(
            entity_type="ClaimRoleMapping",
            action="updated",
            entity_id=mapping_id,
            after=updated_item,
            before=existing,
            metadata={"tenant_id": tenant_id, "app_namespace": app_namespace},
        )

        return self._item_to_mapping(updated_item)

    def delete(
        self, tenant_id: str, app_namespace: str, mapping_id: str
    ) -> None:
        """Delete a mapping.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            mapping_id: Mapping ID
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
        sk_value = f"MAPPING#{mapping_id}"

        # Get the item before deletion for event
        existing = self._get_item({"pk": pk_value, "sk": sk_value})

        self._delete_item({"pk": pk_value, "sk": sk_value})

        # Publish delete event
        if existing:
            self._publisher.publish(
                entity_type="ClaimRoleMapping",
                action="deleted",
                entity_id=mapping_id,
                before=existing,
                metadata={"tenant_id": tenant_id, "app_namespace": app_namespace},
            )

    @staticmethod
    def _item_to_mapping(item: dict[str, Any] | None) -> ClaimRoleMapping | None:
        """Convert a DynamoDB item to a ClaimRoleMapping model.

        Args:
            item: DynamoDB item dictionary

        Returns:
            ClaimRoleMapping model or None if item is None
        """
        if not item:
            return None

        return ClaimRoleMapping(
            id=item["id"],
            tenant_id=item["tenant_id"],
            app_namespace=item["app_namespace"],
            claim_key=item["claim_key"],
            claim_value=item["claim_value"],
            role_id=item["role_id"],
            priority=item.get("priority", 0),
            is_active=item.get("is_active", True),
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )
