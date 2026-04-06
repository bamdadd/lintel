"""Integration tests validating that all API routers mount correctly.

These tests verify the composition root wiring: that ``mount_routers``
registers all expected route prefixes and that the app can be created
without import errors.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.api.app import create_app
from lintel.api.routers import mount_routers


def test_create_app_returns_fastapi_instance() -> None:
    """The app factory must produce a working FastAPI instance."""
    app = create_app()
    assert isinstance(app, FastAPI)


def test_mount_routers_adds_routes() -> None:
    """mount_routers must register at least one route on a fresh app."""
    app = FastAPI()
    mount_routers(app)
    assert len(app.routes) > 0


def test_health_endpoint_reachable() -> None:
    """The /healthz route should be mounted and return 200."""
    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_api_v1_prefix_present() -> None:
    """At least one /api/v1 route must be registered."""
    app = create_app()
    api_routes = [
        r
        for r in app.routes
        if hasattr(r, "path") and str(getattr(r, "path", "")).startswith("/api/v1")
    ]
    assert len(api_routes) > 50, f"Expected 50+ /api/v1 routes, found {len(api_routes)}"


def test_key_route_prefixes_exist() -> None:
    """Spot-check that critical domain route prefixes are mounted."""
    app = create_app()
    paths = {str(getattr(r, "path", "")) for r in app.routes}

    expected_fragments = [
        "/api/v1/users",
        "/api/v1/teams",
        "/api/v1/projects",
        "/api/v1/pipelines",
        "/api/v1/chat",
        "/api/v1/agents",
        "/api/v1/skills",
        "/api/v1/boards",
        "/api/v1/automations",
        "/api/v1/credentials",
    ]
    for fragment in expected_fragments:
        matches = [p for p in paths if fragment in p]
        assert matches, f"No route containing '{fragment}' found in mounted routes"
