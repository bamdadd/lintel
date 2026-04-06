"""Integration tests validating that all API routers are mounted correctly.

These tests verify the composition root wiring without starting the full
lifespan (no stores, no event bus, etc.). They import the router module
directly and check that mount_routers registers the expected route tags.
"""

from __future__ import annotations

from fastapi import FastAPI

from lintel.api.routers import mount_routers


def _get_all_tags(app: FastAPI) -> set[str]:
    """Collect all unique tags from mounted routes."""
    tags: set[str] = set()
    for route in app.routes:
        route_tags = getattr(route, "tags", None)
        if route_tags:
            tags.update(route_tags)
    return tags


def test_mount_routers_registers_routes() -> None:
    """mount_routers adds routes to the app."""
    app = FastAPI()
    mount_routers(app)
    # At a minimum there should be many routes
    api_routes = [r for r in app.routes if hasattr(r, "tags")]
    assert len(api_routes) > 50, f"Expected 50+ routes, got {len(api_routes)}"


def test_core_api_tags_present() -> None:
    """Core API tag groups are present after mounting."""
    app = FastAPI()
    mount_routers(app)
    tags = _get_all_tags(app)

    expected_tags = {
        "health",
        "users",
        "teams",
        "projects",
        "pipelines",
        "chat",
        "workflows",
        "events",
        "settings",
        "auth",
    }
    missing = expected_tags - tags
    assert not missing, f"Missing core tags: {missing}"


def test_extracted_api_tags_present() -> None:
    """Extracted API package tags are present after mounting."""
    app = FastAPI()
    mount_routers(app)
    tags = _get_all_tags(app)

    extracted_tags = {
        "boards",
        "triggers",
        "environments",
        "variables",
        "credentials",
        "audit",
        "approval-requests",
        "artifacts",
        "skills",
        "agents",
        "mcp-servers",
        "models",
        "ai-providers",
        "repositories",
        "compliance",
        "automations",
        "sandboxes",
    }
    missing = extracted_tags - tags
    assert not missing, f"Missing extracted API tags: {missing}"


def test_all_routes_have_api_v1_prefix() -> None:
    """All tagged API routes (except health) are mounted under /api/v1."""
    app = FastAPI()
    mount_routers(app)

    # Health routes live at root (/healthz, /readyz) by convention
    skip_tags = {"health"}

    for route in app.routes:
        path = getattr(route, "path", "")
        route_tags = getattr(route, "tags", None)
        if route_tags and path and not set(route_tags) & skip_tags:
            assert path.startswith("/api/v1"), (
                f"Route {path} with tags {route_tags} not under /api/v1"
            )
