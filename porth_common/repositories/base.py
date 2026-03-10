"""Base DynamoDB repository with shared functionality.

This module provides foundational repository patterns for single-table DynamoDB design,
including helper functions for ID generation, timestamp management, and common CRUD
operations. It abstracts away low-level DynamoDB details while supporting both UUID-based
entity IDs (for users, roles, permissions) and sequential integer IDs (for organizations
and tenants).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key

from porth_common.config import AWS_REGION, DYNAMODB_ENDPOINT


def _get_dynamodb_resource():
    """Get DynamoDB resource, supporting local endpoint for testing."""
    kwargs = {"region_name": AWS_REGION}
    if DYNAMODB_ENDPOINT:
        kwargs["endpoint_url"] = DYNAMODB_ENDPOINT
    return boto3.resource("dynamodb", **kwargs)


def generate_id() -> str:
    """Generate a new UUID for entity IDs.

    Used for User, Role, Permission, and all mapping/configuration entities.
    Provides globally unique identifiers suitable for audit trails and cross-system
    references where sequential numbering is not required.
    """
    return str(uuid.uuid4())


def generate_sequential_id(counter_name: str, table, start_value: int = 1000) -> str:
    """Generate a sequential ID using DynamoDB atomic counter.

    Uses a dedicated counter item in the table to atomically increment and return
    the next available ID. This provides human-friendly, short IDs suitable for
    entities that are frequently referenced in queries, logs, and debugging
    (e.g., Organization and Tenant IDs).

    The counter item is stored with PK=COUNTER#{counter_name}, SK=COUNTER.
    On first invocation, the counter initialises at start_value (default 1000).
    Subsequent calls increment by 1 (1001, 1002, ...).

    Thread-safe: uses DynamoDB's atomic SET/ADD operations with condition expressions
    to prevent duplicate IDs even under concurrent access.

    Args:
        counter_name: Unique name for this counter (e.g., 'ORG', 'TENANT')
        table: DynamoDB Table resource to store the counter in
        start_value: Starting value for new counters (default 1000)

    Returns:
        String representation of the next sequential ID (e.g., '1000', '1001')
    """
    try:
        # Try to increment existing counter by 1
        response = table.update_item(
            Key={"PK": f"COUNTER#{counter_name}", "SK": "COUNTER"},
            UpdateExpression="SET current_value = current_value + :inc",
            ExpressionAttributeValues={":inc": 1},
            ConditionExpression="attribute_exists(current_value)",
            ReturnValues="UPDATED_NEW",
        )
        return str(int(response["Attributes"]["current_value"]))
    except table.meta.client.exceptions.ConditionalCheckFailedException:
        # Counter doesn't exist yet — initialise it at start_value
        table.put_item(
            Item={
                "PK": f"COUNTER#{counter_name}",
                "SK": "COUNTER",
                "current_value": start_value,
            }
        )
        return str(start_value)


def utc_now() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


class BaseRepository:
    """Base class for DynamoDB repositories implementing single-table design patterns.

    Provides common CRUD operations (put, get, update, delete, query) and pagination
    support for both main table and Global Secondary Index queries. All subclasses
    inherit these methods, which handle:
    - Low-level DynamoDB API interaction (put_item, get_item, update_item, delete_item, query)
    - Automatic pagination for queries and GSI scans
    - Expression attribute name/value escaping to avoid keyword conflicts
    - Flexible filtering via filter expressions

    The single-table design stores multiple entity types in one table with composite keys
    (PK, SK) and uses GSIs for alternative access patterns. Subclasses manage their own
    entity-specific PK/SK naming schemes and GSI definitions.
    """

    def __init__(self, table_name: str, dynamodb_resource=None):
        """Initialize repository with a DynamoDB table.

        Args:
            table_name: Name of the DynamoDB table to operate on
            dynamodb_resource: Optional boto3 DynamoDB resource for dependency injection
                             (useful for testing with mocked resources)
        """
        self._dynamodb = dynamodb_resource or _get_dynamodb_resource()
        self._table = self._dynamodb.Table(table_name)

    @property
    def table(self):
        """Access the underlying DynamoDB Table resource."""
        return self._table

    def _put_item(self, item: dict[str, Any]) -> dict[str, Any]:
        """Put an item into the table.

        Args:
            item: Dictionary representing the item to store (must include PK and SK keys)

        Returns:
            The item that was stored (same as input)
        """
        self._table.put_item(Item=item)
        return item

    def _get_item(self, key: dict[str, Any]) -> dict[str, Any] | None:
        """Get a single item by primary key.

        Args:
            key: Dictionary with PK and SK (e.g., {"PK": "ORG#1000", "SK": "METADATA"})

        Returns:
            The item if found, None otherwise
        """
        response = self._table.get_item(Key=key)
        return response.get("Item")

    def _update_item(
        self,
        key: dict[str, Any],
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        """Update specific attributes on an item.

        Automatically handles expression attribute names to avoid keyword conflicts
        and provides clean API for setting multiple attributes at once.

        Args:
            key: Dictionary with PK and SK identifying the item
            updates: Dictionary of {attribute_name: new_value} to update

        Returns:
            The updated item with all attributes (from UPDATED_NEW response)
        """
        update_parts = []
        expression_values = {}
        expression_names = {}

        for i, (attr, value) in enumerate(updates.items()):
            placeholder = f":v{i}"
            name_placeholder = f"#a{i}"
            update_parts.append(f"{name_placeholder} = {placeholder}")
            expression_values[placeholder] = value
            expression_names[name_placeholder] = attr

        update_expression = "SET " + ", ".join(update_parts)

        response = self._table.update_item(
            Key=key,
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values,
            ExpressionAttributeNames=expression_names,
            ReturnValues="ALL_NEW",
        )
        return response.get("Attributes", {})

    def _delete_item(self, key: dict[str, Any]) -> None:
        """Delete an item by primary key.

        Args:
            key: Dictionary with PK and SK identifying the item to delete
        """
        self._table.delete_item(Key=key)

    def _query(
        self,
        key_condition,
        index_name: str | None = None,
        filter_expression=None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query items with a key condition expression.

        Automatically handles pagination by iterating through all results.

        Args:
            key_condition: boto3 KeyConditionExpression (e.g., Key("PK").eq("ORG#1000"))
            index_name: Optional GSI name to query (if None, queries main table)
            filter_expression: Optional filter to apply after key condition
            limit: Maximum number of items to return (pagination handled automatically)

        Returns:
            List of items matching the key condition and filter
        """
        kwargs: dict[str, Any] = {"KeyConditionExpression": key_condition}
        if index_name:
            kwargs["IndexName"] = index_name
        if filter_expression:
            kwargs["FilterExpression"] = filter_expression
        if limit:
            kwargs["Limit"] = limit

        items = []
        while True:
            response = self._table.query(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
            if limit and len(items) >= limit:
                break

        return items[:limit] if limit else items

    def _query_gsi(
        self,
        index_name: str,
        key_condition,
        filter_expression=None,
    ) -> list[dict[str, Any]]:
        """Query a Global Secondary Index.

        Convenience wrapper around _query() for GSI queries.

        Args:
            index_name: Name of the GSI to query (required)
            key_condition: boto3 KeyConditionExpression
            filter_expression: Optional filter to apply after key condition

        Returns:
            List of items matching the key condition on the GSI
        """
        return self._query(
            key_condition,
            index_name=index_name,
            filter_expression=filter_expression,
        )
