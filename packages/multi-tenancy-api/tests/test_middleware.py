"""Tests for workspace isolation middleware."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from lintel.multi_tenancy_api.middleware import WORKSPACE_HEADER, WorkspaceIsolationMiddleware

if TYPE_CHECKING:
    from collections.abc import Callable

    from starlette.responses import Response


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(WorkspaceIsolationMiddleware)

    @app.get("/api/v1/test")
    async def _test(request: Request) -> dict[str, Any]:
        return {"workspace_id": getattr(request.state, "workspace_id", None)}

    @app.get("/healthz")
    async def _health(request: Request) -> dict[str, Any]:
        return {"workspace_id": getattr(request.state, "workspace_id", None)}

    @app.get("/api/v1/workspaces")
    async def _workspaces(request: Request) -> dict[str, Any]:
        return {"workspace_id": getattr(request.state, "workspace_id", None)}

    return app


class TestWorkspaceIsolationMiddleware:
    def test_header_sets_workspace_id(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/test", headers={WORKSPACE_HEADER: "ws-123"})
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] == "ws-123"

    def test_no_header_returns_none(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/test")
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] is None

    def test_jwt_claim_fallback(self) -> None:
        """When no header, falls back to auth_user.workspace_id."""

        @dataclass
        class FakeAuth:
            workspace_id: str = "ws-jwt"

        app = _make_app()

        @app.middleware("http")
        async def inject_auth(
            request: Request,
            call_next: Callable[..., Response],  # type: ignore[type-arg]
        ) -> Response:
            request.state.auth_user = FakeAuth()
            return await call_next(request)

        client = TestClient(app)
        resp = client.get("/api/v1/test")
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] == "ws-jwt"

    def test_header_takes_precedence_over_jwt(self) -> None:
        @dataclass
        class FakeAuth:
            workspace_id: str = "ws-jwt"

        app = _make_app()

        @app.middleware("http")
        async def inject_auth(
            request: Request,
            call_next: Callable[..., Response],  # type: ignore[type-arg]
        ) -> Response:
            request.state.auth_user = FakeAuth()
            return await call_next(request)

        client = TestClient(app)
        resp = client.get(
            "/api/v1/test",
            headers={WORKSPACE_HEADER: "ws-header"},
        )
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] == "ws-header"

    def test_unscoped_paths_get_none(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/healthz", headers={WORKSPACE_HEADER: "ws-123"})
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] is None

    def test_workspace_routes_unscoped(self) -> None:
        app = _make_app()
        client = TestClient(app)
        resp = client.get("/api/v1/workspaces", headers={WORKSPACE_HEADER: "ws-123"})
        assert resp.status_code == 200
        assert resp.json()["workspace_id"] is None
