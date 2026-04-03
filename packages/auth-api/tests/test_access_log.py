"""Tests for API access logging middleware."""

from __future__ import annotations

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.auth_api.access_log import AccessLogMiddleware
from lintel.auth_api.middleware import JWTAuthMiddleware
from lintel.domain.auth.jwt import create_access_token


def _make_app(*, exclude_paths: tuple[str, ...] | None = None) -> FastAPI:
    app = FastAPI()
    # AccessLog must be added first (outermost) so it wraps the full request.
    # JWTAuth runs inside, setting request.state.auth_user before AccessLog reads it.
    kw = {}
    if exclude_paths is not None:
        kw["exclude_paths"] = exclude_paths
    app.add_middleware(AccessLogMiddleware, **kw)
    app.add_middleware(JWTAuthMiddleware)

    @app.get("/api/v1/items")
    async def list_items() -> list[str]:
        return ["a", "b"]

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


class TestAccessLogMiddleware:
    def test_logs_request_with_authenticated_user(self) -> None:
        app = _make_app()
        token = create_access_token("user-42", "admin")
        with (
            patch("lintel.auth_api.access_log._logger") as mock_logger,
            TestClient(app) as client,
        ):
            resp = client.get(
                "/api/v1/items",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert resp.status_code == 200
        mock_logger.info.assert_called_once()
        call_kwargs = mock_logger.info.call_args
        assert call_kwargs[0][0] == "api.access"
        kw = call_kwargs[1]
        assert kw["method"] == "GET"
        assert kw["path"] == "/api/v1/items"
        assert kw["status_code"] == 200
        assert kw["user_id"] == "user-42"
        assert kw["user_role"] == "admin"
        assert "duration_ms" in kw
        assert "client_ip" in kw

    def test_logs_request_without_auth(self) -> None:
        app = _make_app()
        with (
            patch("lintel.auth_api.access_log._logger") as mock_logger,
            TestClient(app) as client,
        ):
            resp = client.get("/api/v1/items")
        assert resp.status_code == 200
        mock_logger.info.assert_called_once()
        kw = mock_logger.info.call_args[1]
        assert kw["user_id"] is None
        assert kw["user_role"] is None

    def test_excludes_healthz_by_default(self) -> None:
        app = _make_app()
        with (
            patch("lintel.auth_api.access_log._logger") as mock_logger,
            TestClient(app) as client,
        ):
            resp = client.get("/healthz")
        assert resp.status_code == 200
        mock_logger.info.assert_not_called()

    def test_custom_exclude_paths(self) -> None:
        app = _make_app(exclude_paths=("/healthz", "/api/v1/items"))
        with (
            patch("lintel.auth_api.access_log._logger") as mock_logger,
            TestClient(app) as client,
        ):
            client.get("/api/v1/items")
            client.get("/healthz")
        mock_logger.info.assert_not_called()

    def test_logs_user_agent(self) -> None:
        app = _make_app()
        with (
            patch("lintel.auth_api.access_log._logger") as mock_logger,
            TestClient(app) as client,
        ):
            client.get("/api/v1/items", headers={"User-Agent": "test-agent/1.0"})
        kw = mock_logger.info.call_args[1]
        assert kw["user_agent"] == "test-agent/1.0"

    def test_logs_error_status(self) -> None:
        app = _make_app()
        with (
            patch("lintel.auth_api.access_log._logger") as mock_logger,
            TestClient(app) as client,
        ):
            resp = client.get("/api/v1/nonexistent")
        assert resp.status_code == 404
        mock_logger.warning.assert_called_once()
        kw = mock_logger.warning.call_args[1]
        assert kw["status_code"] == 404

    def test_duration_is_positive(self) -> None:
        app = _make_app()
        with (
            patch("lintel.auth_api.access_log._logger") as mock_logger,
            TestClient(app) as client,
        ):
            client.get("/api/v1/items")
        kw = mock_logger.info.call_args[1]
        assert kw["duration_ms"] >= 0
