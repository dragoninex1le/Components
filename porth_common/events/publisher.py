"""EventBridge event publisher for porth user management events."""

from __future__ import annotations

import json
from typing import Any

import boto3

from porth_common.config import EVENT_BUS_NAME, EVENT_SOURCE


class EventPublisher:
    """Publishes events to EventBridge for all CRUD operations."""

    def __init__(self, client=None):
        """Initialize with optional mocked EventBridge client."""
        self._client = client or boto3.client("events")

    def publish(
        self,
        source: str,
        detail_type: str,
        detail: dict[str, Any],
        event_bus_name: str = EVENT_BUS_NAME,
    ) -> str:
        """Publish an event to EventBridge.

        Args:
            source: Event source (e.g., 'porth.user-management')
            detail_type: Type of event (e.g., 'Organization.created')
            detail: Event payload as dictionary
            event_bus_name: Target event bus name

        Returns:
            EventId from EventBridge
        """
        response = self._client.put_events(
            Entries=[
                {
                    "Source": source,
                    "DetailType": detail_type,
                    "Detail": json.dumps(detail),
                    "EventBusName": event_bus_name,
                }
            ]
        )

        if response["FailedEntryCount"] > 0:
            raise RuntimeError(
                f"Failed to publish event: {response['Entries'][0].get('ErrorMessage')}"
            )

        return response["Entries"][0]["EventId"]
