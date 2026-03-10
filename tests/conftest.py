"""Shared pytest fixtures for Porth Common tests."""

from __future__ import annotations

import os

import boto3
import pytest
from moto import mock_aws


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables for all tests."""
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_SECURITY_TOKEN", "testing")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "testing")


@pytest.fixture
def dynamodb_resource():
    """Provide a mocked DynamoDB resource."""
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        yield resource


@pytest.fixture
def events_client():
    """Provide a mocked EventBridge client."""
    with mock_aws():
        client = boto3.client("events", region_name="us-east-1")
        client.create_event_bus(Name="porth-events")
        yield client


def create_table(dynamodb_resource, table_name, key_schema, attribute_definitions, gsis=None):
    """Helper to create a DynamoDB table in tests."""
    kwargs = {
        "TableName": table_name,
        "KeySchema": key_schema,
        "AttributeDefinitions": attribute_definitions,
        "BillingMode": "PAY_PER_REQUEST",
    }
    if gsis:
        kwargs["GlobalSecondaryIndexes"] = gsis
    return dynamodb_resource.create_table(**kwargs)
