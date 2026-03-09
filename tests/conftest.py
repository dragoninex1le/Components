"""Shared pytest fixtures for porth-common tests."""

import pytest
from moto import mock_dynamodb, mock_events
from boto3 import client, resource


@pytest.fixture(scope="session")
def aws_credentials():
    """Mock AWS credentials for testing."""
    import os

    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"


@pytest.fixture
def dynamodb(aws_credentials):
    """Create a mocked DynamoDB resource."""
    with mock_dynamodb():
        yield resource("dynamodb", region_name="us-east-1")


@pytest.fixture
def dynamodb_tables(dynamodb):
    """Create DynamoDB tables for testing."""
    tables = {}
    table_configs = [
        (
            "porth-users",
            [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        ),
        (
            "porth-permissions",
            [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        ),
        (
            "porth-roles",
            [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        ),
        (
            "porth-claim-role-mappings",
            [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        ),
        (
            "porth-claim-mapping-configs",
            [{"AttributeName": "PK", "KeyType": "HASH"}, {"AttributeName": "SK", "KeyType": "RANGE"}],
        ),
    ]

    for table_name, key_schema in table_configs:
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=key_schema,
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
        )
        tables[table_name] = table

    return tables


@pytest.fixture
def events_client(aws_credentials):
    """Create a mocked EventBridge client."""
    with mock_events():
        yield client("events", region_name="us-east-1")
