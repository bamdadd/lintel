"""Tests for sub-session endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from fastapi.testclient import TestClient

from lintel.sandboxes_api.sub_session_store import InMemorySubSessionStore
from lintel.sandboxes_api.sub_sessions import sub_session_store_provider


@pytest.fixture()
def sub_session_client() -> Generator[TestClient]:
    from lintel.api.app import create_app
    from lintel.sandboxes_api.routes import SandboxStore

    app = create_app()
    with TestClient(app) as c:
        store = InMemorySubSessionStore()
        sub_session_store_provider.override(store)
        app.state.sandbox_store = SandboxStore()
        yield c


class TestSpawnSubSession:
    def test_spawn(self, sub_session_client: TestClient) -> None:
        resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={
                "parent_pipeline_run_id": "run-1",
                "repo_url": "https://github.com/org/repo",
                "prompt": "research auth patterns",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["parent_pipeline_run_id"] == "run-1"
        assert data["repo_url"] == "https://github.com/org/repo"
        assert data["prompt"] == "research auth patterns"
        assert data["status"] == "pending"
        assert data["session_id"]

    def test_max_sub_sessions(self, sub_session_client: TestClient) -> None:
        for _i in range(10):
            resp = sub_session_client.post(
                "/api/v1/sandboxes/sub-sessions",
                json={"parent_pipeline_run_id": "run-1"},
            )
            assert resp.status_code == 201

        resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        assert resp.status_code == 409


class TestListSubSessions:
    def test_list_requires_pipeline(self, sub_session_client: TestClient) -> None:
        resp = sub_session_client.get("/api/v1/sandboxes/sub-sessions")
        assert resp.status_code == 422  # missing required param

    def test_list_empty(self, sub_session_client: TestClient) -> None:
        resp = sub_session_client.get(
            "/api/v1/sandboxes/sub-sessions",
            params={"parent_pipeline_run_id": "run-1"},
        )
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_filtered(self, sub_session_client: TestClient) -> None:
        sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-2"},
        )
        resp = sub_session_client.get(
            "/api/v1/sandboxes/sub-sessions",
            params={"parent_pipeline_run_id": "run-1"},
        )
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_filter_invalid_status(self, sub_session_client: TestClient) -> None:
        resp = sub_session_client.get(
            "/api/v1/sandboxes/sub-sessions",
            params={"parent_pipeline_run_id": "run-1", "status": "bogus"},
        )
        assert resp.status_code == 400


class TestGetSubSession:
    def test_get_existing(self, sub_session_client: TestClient) -> None:
        create_resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        session_id = create_resp.json()["session_id"]

        resp = sub_session_client.get(f"/api/v1/sandboxes/sub-sessions/{session_id}")
        assert resp.status_code == 200
        assert resp.json()["session_id"] == session_id

    def test_get_not_found(self, sub_session_client: TestClient) -> None:
        resp = sub_session_client.get("/api/v1/sandboxes/sub-sessions/nonexistent")
        assert resp.status_code == 404


class TestGetSubSessionResult:
    def test_get_result(self, sub_session_client: TestClient) -> None:
        create_resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        session_id = create_resp.json()["session_id"]

        # Complete the session
        sub_session_client.patch(
            f"/api/v1/sandboxes/sub-sessions/{session_id}",
            json={"status": "completed", "result": "findings here"},
        )

        resp = sub_session_client.get(
            f"/api/v1/sandboxes/sub-sessions/{session_id}/result",
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"] == "findings here"

    def test_get_result_not_found(self, sub_session_client: TestClient) -> None:
        resp = sub_session_client.get(
            "/api/v1/sandboxes/sub-sessions/nonexistent/result",
        )
        assert resp.status_code == 404


class TestUpdateSubSession:
    def test_update_status(self, sub_session_client: TestClient) -> None:
        create_resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        session_id = create_resp.json()["session_id"]

        resp = sub_session_client.patch(
            f"/api/v1/sandboxes/sub-sessions/{session_id}",
            json={"status": "running"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_complete_with_result(self, sub_session_client: TestClient) -> None:
        create_resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        session_id = create_resp.json()["session_id"]

        resp = sub_session_client.patch(
            f"/api/v1/sandboxes/sub-sessions/{session_id}",
            json={"status": "completed", "result": "auth uses JWT"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["result"] == "auth uses JWT"
        assert data["completed_at"] is not None

    def test_fail_with_error(self, sub_session_client: TestClient) -> None:
        create_resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        session_id = create_resp.json()["session_id"]

        resp = sub_session_client.patch(
            f"/api/v1/sandboxes/sub-sessions/{session_id}",
            json={"status": "failed", "error": "sandbox timeout"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "failed"
        assert resp.json()["error"] == "sandbox timeout"

    def test_invalid_status(self, sub_session_client: TestClient) -> None:
        create_resp = sub_session_client.post(
            "/api/v1/sandboxes/sub-sessions",
            json={"parent_pipeline_run_id": "run-1"},
        )
        session_id = create_resp.json()["session_id"]

        resp = sub_session_client.patch(
            f"/api/v1/sandboxes/sub-sessions/{session_id}",
            json={"status": "bogus"},
        )
        assert resp.status_code == 422

    def test_update_not_found(self, sub_session_client: TestClient) -> None:
        resp = sub_session_client.patch(
            "/api/v1/sandboxes/sub-sessions/nonexistent",
            json={"status": "running"},
        )
        assert resp.status_code == 404
