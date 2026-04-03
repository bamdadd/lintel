"""Tests for session lifecycle (hibernate/resume/terminate) API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from fastapi.testclient import TestClient

from lintel.sandbox.session_lifecycle import SessionLifecycleManager
from lintel.sandboxes_api.routes import SandboxStore
from lintel.sandboxes_api.session_lifecycle import lifecycle_manager_provider


@pytest.fixture()
def lifecycle_client(dummy_sandbox_manager: object) -> Generator[TestClient]:
    from lintel.api.app import create_app

    app = create_app()
    mgr = SessionLifecycleManager()
    lifecycle_manager_provider.override(mgr)
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


class TestHibernateSession:
    def test_hibernate(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        resp = lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "hibernated"
        assert data["snapshot_id"] == "snap-1"
        assert data["hibernated_at"] is not None

    def test_hibernate_auto_registers(self, lifecycle_client: TestClient) -> None:
        """Hibernate should auto-register untracked sandbox."""
        sandbox_id = _create_sandbox(lifecycle_client)
        resp = lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "hibernated"

    def test_hibernate_auto_snapshot_id(self, lifecycle_client: TestClient) -> None:
        """Hibernate with empty snapshot_id generates one."""
        sandbox_id = _create_sandbox(lifecycle_client)
        resp = lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={},
        )
        assert resp.status_code == 200
        assert resp.json()["snapshot_id"].startswith("auto-")

    def test_hibernate_already_hibernated_409(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        resp = lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-2"},
        )
        assert resp.status_code == 409

    def test_hibernate_updates_sandbox_store(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        # Check sandbox store metadata was updated
        resp = lifecycle_client.get("/api/v1/sandboxes")
        sandboxes = resp.json()
        entry = next(s for s in sandboxes if s["sandbox_id"] == sandbox_id)
        assert entry["status"] == "hibernated"
        assert entry["snapshot_id"] == "snap-1"


class TestResumeSession:
    def test_resume_hibernated(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        resp = lifecycle_client.post(f"/api/v1/sandboxes/{sandbox_id}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "resumed"
        assert data["resumed_at"] is not None

    def test_resume_non_hibernated_409(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        # Register session first
        lifecycle_client.put(
            f"/api/v1/sandboxes/{sandbox_id}/timeout-config",
            json={"idle_timeout_seconds": 1800},
        )
        resp = lifecycle_client.post(f"/api/v1/sandboxes/{sandbox_id}/resume")
        assert resp.status_code == 409

    def test_resume_not_found(self, lifecycle_client: TestClient) -> None:
        resp = lifecycle_client.post("/api/v1/sandboxes/nonexistent/resume")
        assert resp.status_code == 404

    def test_resume_updates_sandbox_store(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        lifecycle_client.post(f"/api/v1/sandboxes/{sandbox_id}/resume")
        resp = lifecycle_client.get("/api/v1/sandboxes")
        sandboxes = resp.json()
        entry = next(s for s in sandboxes if s["sandbox_id"] == sandbox_id)
        assert entry["status"] == "running"


class TestTerminateSession:
    def test_terminate_running(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        resp = lifecycle_client.post(f"/api/v1/sandboxes/{sandbox_id}/terminate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["state"] == "terminated"
        assert data["terminated_at"] is not None

    def test_terminate_hibernated(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        resp = lifecycle_client.post(f"/api/v1/sandboxes/{sandbox_id}/terminate")
        assert resp.status_code == 200
        assert resp.json()["state"] == "terminated"

    def test_terminate_already_terminated_409(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        lifecycle_client.post(f"/api/v1/sandboxes/{sandbox_id}/terminate")
        resp = lifecycle_client.post(f"/api/v1/sandboxes/{sandbox_id}/terminate")
        assert resp.status_code == 409


class TestGetSessionLifecycle:
    def test_get_session(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        # Register via timeout-config
        lifecycle_client.put(
            f"/api/v1/sandboxes/{sandbox_id}/timeout-config",
            json={"idle_timeout_seconds": 1800},
        )
        resp = lifecycle_client.get(f"/api/v1/sandboxes/{sandbox_id}/session")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_id"] == sandbox_id
        assert data["state"] == "running"

    def test_get_session_not_found(self, lifecycle_client: TestClient) -> None:
        resp = lifecycle_client.get("/api/v1/sandboxes/nonexistent/session")
        assert resp.status_code == 404


class TestTimeoutConfig:
    def test_update_timeout_config(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        resp = lifecycle_client.put(
            f"/api/v1/sandboxes/{sandbox_id}/timeout-config",
            json={"idle_timeout_seconds": 600, "max_lifetime_seconds": 7200},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["timeout_config"]["idle_timeout_seconds"] == 600
        assert data["timeout_config"]["max_lifetime_seconds"] == 7200


class TestGetSessionCost:
    def test_get_cost(self, lifecycle_client: TestClient) -> None:
        sandbox_id = _create_sandbox(lifecycle_client)
        # Register + hibernate to accumulate some cost
        lifecycle_client.post(
            f"/api/v1/sandboxes/{sandbox_id}/hibernate",
            json={"snapshot_id": "snap-1"},
        )
        resp = lifecycle_client.get(f"/api/v1/sandboxes/{sandbox_id}/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sandbox_id"] == sandbox_id
        assert "cost" in data
        assert "total_cost_units" in data
        assert data["cost"]["cpu_seconds"] >= 0.0

    def test_cost_not_found(self, lifecycle_client: TestClient) -> None:
        resp = lifecycle_client.get("/api/v1/sandboxes/nonexistent/cost")
        assert resp.status_code == 404


class TestIdleAndExpiredEndpoints:
    def test_list_idle_sessions(self, lifecycle_client: TestClient) -> None:
        resp = lifecycle_client.get("/api/v1/sandboxes/sessions/idle")
        assert resp.status_code == 200
        data = resp.json()
        assert "idle_sandbox_ids" in data
        assert "count" in data

    def test_list_expired_sessions(self, lifecycle_client: TestClient) -> None:
        resp = lifecycle_client.get("/api/v1/sandboxes/sessions/expired")
        assert resp.status_code == 200
        data = resp.json()
        assert "expired_sandbox_ids" in data
        assert "count" in data
