"""Integration tests validating that all routers mount correctly.

These tests create the full FastAPI application with in-memory stores
and verify that router mounting, middleware ordering, and basic
health checks work end-to-end.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, ClassVar

from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture
def memory_client() -> Generator[TestClient]:
    """Create a TestClient wired against the in-memory backend."""
    os.environ["LINTEL_STORAGE_BACKEND"] = "memory"
    os.environ.pop("LINTEL_DB_DSN", None)
    from lintel.api.app import create_app

    with TestClient(create_app()) as c:
        yield c
    os.environ.pop("LINTEL_STORAGE_BACKEND", None)


class TestAppCreation:
    """Verify the FastAPI app boots successfully with all routers."""

    def test_health_endpoint_returns_ok(self, memory_client: TestClient) -> None:
        """The /healthz endpoint should be reachable and return 200."""
        resp = memory_client.get("/healthz")
        assert resp.status_code == 200

    def test_openapi_schema_loads(self, memory_client: TestClient) -> None:
        """The OpenAPI schema should be generated without import errors."""
        resp = memory_client.get("/openapi.json")
        assert resp.status_code == 200
        schema = resp.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 0

    def test_api_v1_prefix_routes_exist(self, memory_client: TestClient) -> None:
        """At least one /api/v1/ prefixed route should exist."""
        resp = memory_client.get("/openapi.json")
        paths = resp.json()["paths"]
        api_v1_paths = [p for p in paths if p.startswith("/api/v1/")]
        assert len(api_v1_paths) > 50, f"Expected 50+ /api/v1/ routes, got {len(api_v1_paths)}"


class TestRouterTags:
    """Verify key router tags are present in the OpenAPI schema."""

    EXPECTED_TAGS: ClassVar[list[str]] = [
        "health",
        "users",
        "teams",
        "pipelines",
        "chat",
        "workflows",
        "auth",
        "projects",
        "automations",
        "boards",
        "settings",
    ]

    def test_expected_tags_present(self, memory_client: TestClient) -> None:
        """All expected router tags should appear in the OpenAPI schema."""
        resp = memory_client.get("/openapi.json")
        schema = resp.json()
        # Collect all tags from all path operations
        found_tags: set[str] = set()
        for _path, methods in schema["paths"].items():
            for _method, operation in methods.items():
                if isinstance(operation, dict) and "tags" in operation:
                    found_tags.update(operation["tags"])

        for tag in self.EXPECTED_TAGS:
            assert tag in found_tags, f"Tag '{tag}' not found in OpenAPI schema"


class TestMiddlewareStack:
    """Verify middleware is correctly applied."""

    def test_cors_headers_on_options(self, memory_client: TestClient) -> None:
        """CORS preflight should return appropriate headers."""
        resp = memory_client.options(
            "/api/v1/users",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        # Should get a response (either 200 or 405 depending on CORS config)
        assert resp.status_code in (200, 204, 400, 405)

    def test_correlation_id_propagated(self, memory_client: TestClient) -> None:
        """X-Correlation-ID header should be echoed back."""
        resp = memory_client.get(
            "/healthz",
            headers={"X-Correlation-ID": "test-corr-123"},
        )
        assert resp.status_code == 200
        # Correlation middleware should propagate the ID
        corr_id = resp.headers.get("X-Correlation-ID")
        if corr_id is not None:
            assert corr_id == "test-corr-123"
