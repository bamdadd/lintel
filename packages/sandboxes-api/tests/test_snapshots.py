"""Tests for sandbox session snapshot endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from fastapi.testclient import TestClient

from lintel.sandboxes_api.snapshot_store import InMemorySnapshotStore
from lintel.sandboxes_api.snapshots import snapshot_store_provider


@pytest.fixture()
def snapshot_client(dummy_sandbox_manager: object) -> Generator[TestClient]:
    from lintel.api.app import create_app
    from lintel.sandboxes_api.routes import SandboxStore

    app = create_app()
    with TestClient(app) as c:
        store = InMemorySnapshotStore()
        snapshot_store_provider.override(store)
        app.state.sandbox_manager = dummy_sandbox_manager
        app.state.sandbox_store = SandboxStore()
        yield c


class TestCreateSnapshot:
    def test_creates_snapshot(self, snapshot_client: TestClient) -> None:
        resp = snapshot_client.post(
            "/api/v1/sandboxes/sbx-123/snapshot",
            json={"pipeline_run_id": "run-1", "project_id": "proj-1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sandbox_id"] == "sbx-123"
        assert data["pipeline_run_id"] == "run-1"
        assert data["project_id"] == "proj-1"
        assert data["status"] == "completed"
        assert data["snapshot_id"]
        assert data["image_tag"].startswith("snapshot-")
        assert data["ttl_seconds"] == 86400
        assert data["expires_at"] is not None

    def test_custom_ttl(self, snapshot_client: TestClient) -> None:
        resp = snapshot_client.post(
            "/api/v1/sandboxes/sbx-123/snapshot",
            json={"ttl_seconds": 3600},
        )
        assert resp.status_code == 201
        assert resp.json()["ttl_seconds"] == 3600


class TestListSnapshots:
    def test_list_empty(self, snapshot_client: TestClient) -> None:
        resp = snapshot_client.get("/api/v1/sandboxes/snapshots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_all(self, snapshot_client: TestClient) -> None:
        snapshot_client.post(
            "/api/v1/sandboxes/sbx-1/snapshot",
            json={"project_id": "proj-1"},
        )
        snapshot_client.post(
            "/api/v1/sandboxes/sbx-2/snapshot",
            json={"project_id": "proj-2"},
        )
        resp = snapshot_client.get("/api/v1/sandboxes/snapshots")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_filter_by_project(self, snapshot_client: TestClient) -> None:
        snapshot_client.post(
            "/api/v1/sandboxes/sbx-1/snapshot",
            json={"project_id": "proj-1"},
        )
        snapshot_client.post(
            "/api/v1/sandboxes/sbx-2/snapshot",
            json={"project_id": "proj-2"},
        )
        resp = snapshot_client.get(
            "/api/v1/sandboxes/snapshots",
            params={"project_id": "proj-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["project_id"] == "proj-1"

    def test_filter_by_pipeline_run(self, snapshot_client: TestClient) -> None:
        snapshot_client.post(
            "/api/v1/sandboxes/sbx-1/snapshot",
            json={"pipeline_run_id": "run-1"},
        )
        snapshot_client.post(
            "/api/v1/sandboxes/sbx-2/snapshot",
            json={"pipeline_run_id": "run-2"},
        )
        resp = snapshot_client.get(
            "/api/v1/sandboxes/snapshots",
            params={"pipeline_run_id": "run-1"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_by_invalid_status(self, snapshot_client: TestClient) -> None:
        resp = snapshot_client.get(
            "/api/v1/sandboxes/snapshots",
            params={"status": "bogus"},
        )
        assert resp.status_code == 400


class TestGetSnapshot:
    def test_get_existing(self, snapshot_client: TestClient) -> None:
        create_resp = snapshot_client.post(
            "/api/v1/sandboxes/sbx-1/snapshot",
            json={"project_id": "proj-1"},
        )
        snapshot_id = create_resp.json()["snapshot_id"]

        resp = snapshot_client.get(f"/api/v1/sandboxes/snapshots/{snapshot_id}")
        assert resp.status_code == 200
        assert resp.json()["snapshot_id"] == snapshot_id

    def test_get_not_found(self, snapshot_client: TestClient) -> None:
        resp = snapshot_client.get("/api/v1/sandboxes/snapshots/nonexistent")
        assert resp.status_code == 404


class TestRestoreSnapshot:
    def test_restore(self, snapshot_client: TestClient) -> None:
        create_resp = snapshot_client.post(
            "/api/v1/sandboxes/sbx-1/snapshot",
            json={"project_id": "proj-1"},
        )
        snapshot_id = create_resp.json()["snapshot_id"]

        resp = snapshot_client.post(
            f"/api/v1/sandboxes/snapshots/{snapshot_id}/restore",
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["snapshot_id"] == snapshot_id
        assert data["restored_sandbox_id"].startswith("restored-")

    def test_restore_not_found(self, snapshot_client: TestClient) -> None:
        resp = snapshot_client.post(
            "/api/v1/sandboxes/snapshots/nonexistent/restore",
        )
        assert resp.status_code == 404


class TestDeleteSnapshot:
    def test_delete(self, snapshot_client: TestClient) -> None:
        create_resp = snapshot_client.post(
            "/api/v1/sandboxes/sbx-1/snapshot",
            json={},
        )
        snapshot_id = create_resp.json()["snapshot_id"]

        resp = snapshot_client.delete(f"/api/v1/sandboxes/snapshots/{snapshot_id}")
        assert resp.status_code == 204

        # Verify gone
        resp = snapshot_client.get(f"/api/v1/sandboxes/snapshots/{snapshot_id}")
        assert resp.status_code == 404

    def test_delete_not_found(self, snapshot_client: TestClient) -> None:
        resp = snapshot_client.delete("/api/v1/sandboxes/snapshots/nonexistent")
        assert resp.status_code == 404
