"""Integration tests for router mounting and app composition.

Validates that all API routers are correctly mounted on the FastAPI app
and that the application can be instantiated without import errors.
"""

from __future__ import annotations


def _make_app_with_routers() -> object:
    """Create a bare FastAPI app and mount all routers.

    Uses lazy imports so that pytest can collect this module even when
    the ``lintel`` namespace is not resolvable at import time (e.g. when
    running ``pytest`` without ``--package lintel``).
    """
    from fastapi import FastAPI

    from lintel.api.routers import mount_routers

    app = FastAPI()
    mount_routers(app)
    return app


def test_mount_routers_succeeds() -> None:
    """Verify that mount_routers() completes without import or wiring errors."""
    app = _make_app_with_routers()

    # Ensure routers were actually mounted (not an empty app)
    routes = getattr(app, "routes", [])
    assert len(routes) > 10, f"Expected many routes, got {len(routes)}"


def test_all_expected_tags_present() -> None:
    """Every extracted API package should contribute at least one tagged route."""
    app = _make_app_with_routers()

    # Collect all tags from mounted routes
    tags: set[str] = set()
    for route in getattr(app, "routes", []):
        route_tags = getattr(route, "tags", None)
        if route_tags:
            tags.update(route_tags)

    # Spot-check critical domain tags that must always be present
    expected_tags = {
        "health",
        "threads",
        "workflows",
        "pipelines",
        "chat",
        "users",
        "teams",
        "projects",
        "boards",
        "agents",
        "models",
        "settings",
        "auth",
        "sandboxes",
        "credentials",
        "audit",
        "approvals",
        "approval-requests",
        "triggers",
        "variables",
        "environments",
        "notifications",
        "skills",
        "mcp-servers",
        "ai-providers",
        "repositories",
        "automations",
        "compliance",
        "experimentation",
    }

    missing = expected_tags - tags
    assert not missing, f"Missing router tags: {missing}"


def test_api_v1_prefix_on_domain_routes() -> None:
    """Non-health routes should be mounted under /api/v1."""
    app = _make_app_with_routers()

    api_paths = [getattr(r, "path", "") for r in getattr(app, "routes", []) if hasattr(r, "path")]
    # At least some routes should start with /api/v1
    v1_routes = [p for p in api_paths if p.startswith("/api/v1")]
    assert len(v1_routes) > 50, f"Expected >50 /api/v1 routes, got {len(v1_routes)}"
