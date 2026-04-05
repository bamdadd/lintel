"""Tests for sandbox preview endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from fastapi.testclient import TestClient

from lintel.api.app import create_app
from lintel.sandboxes_api.routes import SandboxStore


@pytest.fixture()
def client(dummy_sandbox_manager: object) -> Generator[TestClient]:
    app = create_app()
    with TestClient(app) as c:
        app.state.sandbox_manager = dummy_sandbox_manager
        app.state.sandbox_store = SandboxStore()
        yield c


def _create_sandbox(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/sandboxes",
        json={"workspace_id": "ws1", "channel_id": "ch1", "thread_ts": "1.0"},
    )
    assert resp.status_code == 201
    return resp.json()["sandbox_id"]


class TestStartPreview:
    def test_starts_preview(self, client: TestClient) -> None:
        sandbox_id = _create_sandbox(client)
        resp = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/preview",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["preview_url"] == "http://localhost:9999"
        assert data["sandbox_id"] == sandbox_id
        assert data["framework"] == "node"
        assert "started_at" in data

    def test_starts_preview_with_custom_command(self, client: TestClient) -> None:
        sandbox_id = _create_sandbox(client)
        resp = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/preview",
            json={"command": "python -m http.server 8080", "port": 8080},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["container_port"] == 8080

    def test_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes/nonexistent/preview",
            json={},
        )
        assert resp.status_code == 404


class TestGetPreview:
    def test_returns_running_preview(self, client: TestClient) -> None:
        sandbox_id = _create_sandbox(client)
        client.post(f"/api/v1/sandboxes/{sandbox_id}/preview", json={})

        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}/preview")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["preview_url"] == "http://localhost:9999"

    def test_returns_stopped_when_no_preview(self, client: TestClient) -> None:
        sandbox_id = _create_sandbox(client)
        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}/preview")
        assert resp.status_code == 200
        assert resp.json()["status"] == "stopped"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandboxes/nonexistent/preview")
        assert resp.status_code == 404


class TestStopPreview:
    def test_stops_preview(self, client: TestClient) -> None:
        sandbox_id = _create_sandbox(client)
        client.post(f"/api/v1/sandboxes/{sandbox_id}/preview", json={})

        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}/preview")
        assert resp.status_code == 204

        # Verify stopped
        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}/preview")
        assert resp.json()["status"] == "stopped"

    def test_stop_idempotent(self, client: TestClient) -> None:
        sandbox_id = _create_sandbox(client)
        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}/preview")
        assert resp.status_code == 204

    def test_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/sandboxes/nonexistent/preview")
        assert resp.status_code == 404


class TestPreviewCleanupOnDestroy:
    def test_destroy_cleans_preview(self, client: TestClient) -> None:
        sandbox_id = _create_sandbox(client)
        client.post(f"/api/v1/sandboxes/{sandbox_id}/preview", json={})

        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 204
