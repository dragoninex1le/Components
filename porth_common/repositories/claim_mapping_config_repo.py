"""DynamoDB repository for ClaimMappingConfig entities.

Implements versioned claim mapping configuration persistence. Supports saving new versions,
retrieving specific versions or latest, rolling back to previous versions, and validating
configurations against example JWTs.

The single-table design stores versioned configs with:
  - PK: TENANT#{tenant_id}#NS#{app_namespace}, SK: VERSION#{version:06d}
  - GSI1: gsi1pk=TENANT#{tenant_id}, gsi1sk=NS#{app_namespace}#VERSION#{version:06d}
"""

from __future__ import annotations

from typing import Any

from boto3.dynamodb.conditions import Key

from porth_common.config import TABLE_PORTH_CLAIM_MAPPING_CONFIGS
from porth_common.events.publisher import EventPublisher
from porth_common.models.claim_mapping_config import ClaimMappingConfig
from porth_common.repositories.base import BaseRepository, generate_id, utc_now


class ClaimMappingConfigRepository(BaseRepository):
    """Repository for managing claim mapping configurations in DynamoDB.

    Persistence layer for JWT claim transformation pipelines. Stores versioned
    configurations enabling audit trails, change detection, and rollback without
    data loss.

    Single-table design with "porth-claim-mapping-configs" table:
    - Main: PK: TENANT#{tenant_id}#NS#{app_namespace}, SK: VERSION#{version:06d}
    - Listing: GSI1 gsi1pk=TENANT#{tenant_id}, gsi1sk=NS#{app_namespace}#VERSION#{version:06d}

    Features:
    - Automatic version incrementing (version is auto-generated)
    - Efficient latest-version retrieval
    - Immutable historical versions (no updates, only new versions)
    - Rollback: creates new version from historical config
    - Integrity checking via compiled_hash (SHA256 of compiled_ops)
    - Validation results and example JWT stored for audit
    - Event publishing for configuration changes
    """

    def __init__(
        self,
        table_name: str = TABLE_PORTH_CLAIM_MAPPING_CONFIGS,
        dynamodb_resource=None,
        event_publisher: EventPublisher | None = None,
    ):
        """Initialize the repository.

        Args:
            table_name: DynamoDB table name
            dynamodb_resource: Optional mocked DynamoDB resource for testing
            event_publisher: Optional EventPublisher for publishing events
        """
        super().__init__(table_name, dynamodb_resource)
        self._event_publisher = event_publisher or EventPublisher()

    def save(
        self,
        tenant_id: str,
        app_namespace: str,
        mapping_source: dict[str, Any],
        compiled_ops: list[dict[str, Any]],
        compiled_hash: str,
        example_jwt: dict[str, Any] | None = None,
        validation_report: dict[str, Any] | None = None,
    ) -> ClaimMappingConfig:
        """Save a new version of the claim mapping config.

        Auto-increments the version number based on the latest existing version.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            mapping_source: Human-readable mapping configuration
            compiled_ops: Compiled operations list
            compiled_hash: SHA256 hash of compiled ops
            example_jwt: Optional example JWT used for validation
            validation_report: Optional validation results

        Returns:
            ClaimMappingConfig: The saved configuration entity

        Publishes:
            ClaimMappingConfig.created event
        """
        # Get the latest version for this tenant+namespace
        latest_version = self._get_latest_version(tenant_id, app_namespace)
        new_version = latest_version + 1 if latest_version is not None else 1

        config_id = generate_id()
        now = utc_now()

        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
        sk_value = f"VERSION#{str(new_version).zfill(6)}"
        gsi1pk_value = f"TENANT#{tenant_id}"
        gsi1sk_value = f"NS#{app_namespace}#VERSION#{str(new_version).zfill(6)}"

        item: dict[str, Any] = {
            "PK": pk_value,
            "SK": sk_value,
            "gsi1pk": gsi1pk_value,
            "gsi1sk": gsi1sk_value,
            "id": config_id,
            "tenant_id": tenant_id,
            "app_namespace": app_namespace,
            "version": new_version,
            "mapping_source": mapping_source,
            "compiled_ops": compiled_ops,
            "compiled_hash": compiled_hash,
            "compiled_at": now,
            "created_at": now,
            "updated_at": now,
        }

        if example_jwt is not None:
            item["example_jwt"] = example_jwt

        if validation_report is not None:
            item["validation_report"] = validation_report

        self._put_item(item)

        config = self._item_to_config(item)

        self._event_publisher.publish(
            entity_type="ClaimMappingConfig",
            action="created",
            entity_id=config_id,
            after=self._config_to_dict(config),
            metadata={
                "tenant_id": tenant_id,
                "app_namespace": app_namespace,
                "version": new_version,
            },
        )

        return config

    def get_latest(
        self, tenant_id: str, app_namespace: str
    ) -> ClaimMappingConfig | None:
        """Get the latest version of the claim mapping config.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace

        Returns:
            ClaimMappingConfig if found, None otherwise
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"

        # Query with reverse order to get the latest (highest version first)
        items = self._query(
            key_condition=Key("PK").eq(pk_value),
            limit=1,
        )

        # The query returns items in ascending order by default, so get the last one
        if not items:
            return None

        # Need to query in reverse to get the latest
        items = self._query(
            key_condition=Key("PK").eq(pk_value),
        )

        if not items:
            return None

        # Get the last item (highest version)
        latest_item = items[-1]
        return self._item_to_config(latest_item)

    def get_version(
        self, tenant_id: str, app_namespace: str, version: int
    ) -> ClaimMappingConfig | None:
        """Get a specific version of the claim mapping config.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            version: Version number

        Returns:
            ClaimMappingConfig if found, None otherwise
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"
        sk_value = f"VERSION#{str(version).zfill(6)}"

        item = self._get_item({"PK": pk_value, "SK": sk_value})
        return self._item_to_config(item) if item else None

    def list_versions(
        self, tenant_id: str, app_namespace: str
    ) -> list[ClaimMappingConfig]:
        """List all versions of the claim mapping config for a tenant and namespace.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace

        Returns:
            List of ClaimMappingConfig entities, ordered by version ascending
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"

        items = self._query(
            key_condition=Key("PK").eq(pk_value),
        )

        return [self._item_to_config(item) for item in items if item]

    def rollback(
        self, tenant_id: str, app_namespace: str, target_version: int
    ) -> ClaimMappingConfig:
        """Rollback to a previous version by copying it as a new version.

        Does not delete the current version. Creates a new version with the
        configuration from the target version.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace
            target_version: Version to rollback to

        Returns:
            ClaimMappingConfig: The new version created from the rollback

        Raises:
            ValueError: If target version is not found
        """
        # Get the target version
        target_config = self.get_version(tenant_id, app_namespace, target_version)
        if target_config is None:
            raise ValueError(
                f"Version {target_version} not found for {tenant_id}/{app_namespace}"
            )

        # Save as new version (auto-increments)
        new_config = self.save(
            tenant_id=tenant_id,
            app_namespace=app_namespace,
            mapping_source=target_config.mapping_source,
            compiled_ops=target_config.compiled_ops,
            compiled_hash=target_config.compiled_hash,
            example_jwt=target_config.example_jwt,
            validation_report=target_config.validation_report,
        )

        # Publish rollback event
        self._event_publisher.publish(
            entity_type="ClaimMappingConfig",
            action="rolled_back",
            entity_id=new_config.id,
            after=self._config_to_dict(new_config),
            metadata={
                "tenant_id": tenant_id,
                "app_namespace": app_namespace,
                "rolled_back_from_version": target_version,
                "new_version": new_config.version,
            },
        )

        return new_config

    def _get_latest_version(self, tenant_id: str, app_namespace: str) -> int | None:
        """Get the latest version number for a tenant and namespace.

        Args:
            tenant_id: Tenant identifier
            app_namespace: Application namespace

        Returns:
            Latest version number, or None if no versions exist
        """
        pk_value = f"TENANT#{tenant_id}#NS#{app_namespace}"

        items = self._query(
            key_condition=Key("PK").eq(pk_value),
        )

        if not items:
            return None

        # Get the last item (highest version)
        latest_item = items[-1]
        return latest_item.get("version")

    @staticmethod
    def _item_to_config(item: dict[str, Any] | None) -> ClaimMappingConfig | None:
        """Convert a DynamoDB item to a ClaimMappingConfig model.

        Args:
            item: DynamoDB item dictionary

        Returns:
            ClaimMappingConfig model or None if item is None
        """
        if not item:
            return None

        return ClaimMappingConfig(
            id=item["id"],
            tenant_id=item["tenant_id"],
            app_namespace=item["app_namespace"],
            version=item["version"],
            mapping_source=item["mapping_source"],
            compiled_ops=item["compiled_ops"],
            compiled_hash=item["compiled_hash"],
            example_jwt=item.get("example_jwt"),
            validation_report=item.get("validation_report"),
            compiled_at=item["compiled_at"],
            created_at=item["created_at"],
            updated_at=item["updated_at"],
        )

    @staticmethod
    def _config_to_dict(config: ClaimMappingConfig) -> dict[str, Any]:
        """Convert a ClaimMappingConfig model to a dictionary for events.

        Args:
            config: ClaimMappingConfig model

        Returns:
            Dictionary representation of the config
        """
        return config.model_dump()
