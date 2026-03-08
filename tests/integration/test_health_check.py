"""Integration tests for the deployed health check API.

These tests run against the live deployed endpoint after a successful
CloudFormation deployment. The API_ENDPOINT environment variable must
be set to the base URL of the API Gateway.
"""

import json
import os
import time
from datetime import datetime, timezone

import pytest
import requests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def api_endpoint():
    """Base URL of the deployed API Gateway (no trailing slash)."""
    url = os.environ.get("API_ENDPOINT", "").rstrip("/")
    if not url:
        pytest.skip("API_ENDPOINT not set — skipping integration tests")
    return url


@pytest.fixture(scope="session")
def health_url(api_endpoint):
    return f"{api_endpoint}/health"


@pytest.fixture(scope="session")
def health_response(health_url):
    """Fetch the health endpoint once and share across tests."""
    resp = requests.get(health_url, timeout=10)
    return resp


# ---------------------------------------------------------------------------
# Response basics
# ---------------------------------------------------------------------------

class TestHealthEndpointBasics:
    """Verify the health endpoint returns a valid HTTP response."""

    def test_status_code_is_200(self, health_response):
        assert health_response.status_code == 200

    def test_content_type_is_json(self, health_response):
        ct = health_response.headers.get("Content-Type", "")
        assert "application/json" in ct

    def test_response_is_valid_json(self, health_response):
        # Should not raise
        health_response.json()


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestHealthResponseSchema:
    """Verify the JSON body contains all required fields."""

    REQUIRED_FIELDS = ["status", "component", "timestamp", "region"]

    def test_all_required_fields_present(self, health_response):
        body = health_response.json()
        for field in self.REQUIRED_FIELDS:
            assert field in body, f"Missing required field: {field}"

    def test_no_unexpected_fields(self, health_response):
        body = health_response.json()
        allowed = set(self.REQUIRED_FIELDS)
        extra = set(body.keys()) - allowed
        # Not a hard fail — just a warning if new fields appear
        if extra:
            pytest.warns(UserWarning, match=f"Unexpected fields: {extra}")


# ---------------------------------------------------------------------------
# Field value validation
# ---------------------------------------------------------------------------

class TestHealthResponseValues:
    """Verify field values are correct and well-formed."""

    def test_status_is_healthy(self, health_response):
        body = health_response.json()
        assert body["status"] == "healthy"

    def test_component_is_correct(self, health_response):
        body = health_response.json()
        assert body["component"] == "porth-common-components"

    def test_region_is_us_east_1(self, health_response):
        body = health_response.json()
        assert body["region"] == "us-east-1"

    def test_timestamp_is_valid_iso8601(self, health_response):
        body = health_response.json()
        ts = body["timestamp"]
        # Should parse without error
        parsed = datetime.fromisoformat(ts)
        # Should be timezone-aware
        assert parsed.tzinfo is not None, "Timestamp should be timezone-aware"

    def test_timestamp_is_recent(self, health_response):
        """Timestamp should be within the last 60 seconds."""
        body = health_response.json()
        parsed = datetime.fromisoformat(body["timestamp"])
        now = datetime.now(timezone.utc)
        delta = abs((now - parsed).total_seconds())
        assert delta < 60, f"Timestamp is {delta:.0f}s old — expected < 60s"


# ---------------------------------------------------------------------------
# CORS headers
# ---------------------------------------------------------------------------

class TestCORSHeaders:
    """Verify CORS is configured correctly."""

    def test_access_control_allow_origin(self, health_url):
        resp = requests.get(
            health_url,
            headers={"Origin": "https://example.com"},
            timeout=10,
        )
        acao = resp.headers.get("Access-Control-Allow-Origin", "")
        assert acao == "*", f"Expected ACAO='*', got '{acao}'"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorPaths:
    """Verify non-existent routes return appropriate errors."""

    def test_unknown_route_returns_not_found(self, api_endpoint):
        resp = requests.get(f"{api_endpoint}/nonexistent", timeout=10)
        # API Gateway returns 404 for unmatched routes
        assert resp.status_code in (403, 404), (
            f"Expected 403 or 404 for unknown route, got {resp.status_code}"
        )


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestPerformance:
    """Basic performance checks."""

    def test_response_time_under_3_seconds(self, health_url):
        start = time.monotonic()
        requests.get(health_url, timeout=10)
        elapsed = time.monotonic() - start
        assert elapsed < 3.0, f"Response took {elapsed:.2f}s — expected < 3s"

    def test_consecutive_requests_are_consistent(self, health_url):
        """Two back-to-back requests should both succeed."""
        r1 = requests.get(health_url, timeout=10)
        r2 = requests.get(health_url, timeout=10)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r1.json()["status"] == r2.json()["status"]
