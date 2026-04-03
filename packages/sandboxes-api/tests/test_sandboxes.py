"""Tests for the sandbox API endpoints."""

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


@pytest.fixture()
def client_with_openshell(
    sandbox_manager_factory: type,
) -> Generator[TestClient]:
    """Client with both Docker and OpenShell managers available."""
    app = create_app()
    with TestClient(app) as c:
        app.state.sandbox_manager = sandbox_manager_factory()
        app.state.openshell_manager = sandbox_manager_factory()
        app.state.sandbox_store = SandboxStore()
        yield c


class TestCreateSandbox:
    def test_creates_sandbox(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "sandbox_id" in data

    def test_preset_mounts_resolved(self, client: TestClient) -> None:
        """Claude-code preset has no mounts (credentials injected at runtime)."""

        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "preset": "claude-code",
            },
        )
        assert resp.status_code == 201
        sandbox_id = resp.json()["sandbox_id"]

        # Verify no mounts (preset has empty mounts list)
        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        assert len(config.mounts) == 0

        # Verify no mounts in stored metadata
        meta_resp = client.get("/api/v1/sandboxes")
        sandboxes = meta_resp.json()
        entry = next(s for s in sandboxes if s["sandbox_id"] == sandbox_id)
        assert len(entry["mounts"]) == 0

    def test_request_level_mounts(self, client: TestClient) -> None:
        """Mounts passed in request body should be resolved and applied."""
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "mounts": [
                    {"source": "/tmp/test-mount", "target": "/mnt/data", "type": "bind"},
                ],
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        assert len(config.mounts) == 1
        assert config.mounts[0] == ("/tmp/test-mount", "/mnt/data", "bind")

    def test_preset_and_request_mounts_merged(self, client: TestClient) -> None:
        """Request mounts should be applied even with a preset that has no mounts."""
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "preset": "claude-code",
                "mounts": [
                    {"source": "/tmp/extra", "target": "/mnt/extra"},
                ],
            },
        )
        assert resp.status_code == 201

        manager = client.app.state.sandbox_manager  # type: ignore[union-attr]
        config = manager.last_config
        assert len(config.mounts) == 1
        targets = {m[1] for m in config.mounts}
        assert "/mnt/extra" in targets


class TestGetSandboxStatus:
    def test_returns_status(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={"workspace_id": "ws1", "channel_id": "ch1", "thread_ts": "1.0"},
        )
        sandbox_id = resp.json()["sandbox_id"]

        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandboxes/nonexistent")
        assert resp.status_code == 404


class TestExecuteCommand:
    def test_executes_command(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={"workspace_id": "ws1", "channel_id": "ch1", "thread_ts": "1.0"},
        )
        sandbox_id = resp.json()["sandbox_id"]

        resp = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/execute",
            json={"command": "echo hello"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["exit_code"] == 0
        assert data["stdout"] == "ok\n"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes/nonexistent/execute",
            json={"command": "echo hello"},
        )
        assert resp.status_code == 404


class TestWriteAndReadFile:
    def test_write_then_read(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={"workspace_id": "ws1", "channel_id": "ch1", "thread_ts": "1.0"},
        )
        sandbox_id = resp.json()["sandbox_id"]

        resp = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/files",
            json={"path": "/workspace/f.txt", "content": "hello"},
        )
        assert resp.status_code == 200

        resp = client.get(
            f"/api/v1/sandboxes/{sandbox_id}/files",
            params={"path": "/workspace/f.txt"},
        )
        assert resp.status_code == 200
        assert resp.json()["content"] == "hello"


class TestCleanupWorkspace:
    def test_cleans_workspace(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={"workspace_id": "ws1", "channel_id": "ch1", "thread_ts": "1.0"},
        )
        sandbox_id = resp.json()["sandbox_id"]

        resp = client.post(f"/api/v1/sandboxes/{sandbox_id}/cleanup-workspace")
        assert resp.status_code == 200
        assert resp.json()["status"] == "cleaned"

    def test_not_found(self, client: TestClient) -> None:
        resp = client.post("/api/v1/sandboxes/nonexistent/cleanup-workspace")
        assert resp.status_code == 404


class TestDestroySandbox:
    def test_destroys(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={"workspace_id": "ws1", "channel_id": "ch1", "thread_ts": "1.0"},
        )
        sandbox_id = resp.json()["sandbox_id"]

        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 204

    def test_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/sandboxes/nonexistent")
        assert resp.status_code == 404


class TestOpenShellBackendRouting:
    def test_create_with_openshell_backend(self, client_with_openshell: TestClient) -> None:
        resp = client_with_openshell.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "backend": "openshell",
            },
        )
        assert resp.status_code == 201
        sandbox_id = resp.json()["sandbox_id"]

        # Verify stored metadata has backend=openshell
        list_resp = client_with_openshell.get("/api/v1/sandboxes")
        entry = next(s for s in list_resp.json() if s["sandbox_id"] == sandbox_id)
        assert entry["backend"] == "openshell"

    def test_create_openshell_lazy_init(
        self,
        client: TestClient,
        sandbox_manager_factory: type,
    ) -> None:
        """OpenShell manager is lazily created when not pre-configured."""
        from unittest.mock import patch

        dummy = sandbox_manager_factory()
        with patch(
            "lintel.sandbox.openshell_backend.OpenShellSandboxManager",
            return_value=dummy,
        ):
            resp = client.post(
                "/api/v1/sandboxes",
                json={
                    "workspace_id": "ws1",
                    "channel_id": "ch1",
                    "thread_ts": "1.0",
                    "backend": "openshell",
                },
            )
        assert resp.status_code == 201
        assert "sandbox_id" in resp.json()

    def test_create_unknown_backend(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "backend": "unknown",
            },
        )
        assert resp.status_code == 400
        assert "Unknown backend" in resp.json()["detail"]

    def test_resolve_manager_routes_to_openshell(self, client_with_openshell: TestClient) -> None:
        """Status/destroy should use the openshell manager for openshell sandboxes."""
        resp = client_with_openshell.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "backend": "openshell",
            },
        )
        sandbox_id = resp.json()["sandbox_id"]

        # get_status should route to openshell manager
        status_resp = client_with_openshell.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert status_resp.status_code == 200
        assert status_resp.json()["status"] == "running"

        # destroy should route to openshell manager
        del_resp = client_with_openshell.delete(f"/api/v1/sandboxes/{sandbox_id}")
        assert del_resp.status_code == 204

    def test_cleanup_unassigned_mixed_backends(self, client_with_openshell: TestClient) -> None:
        """Cleanup should use the correct manager for each sandbox's backend."""
        # Create a Docker sandbox
        resp1 = client_with_openshell.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "1.0",
                "backend": "docker",
            },
        )
        assert resp1.status_code == 201

        # Create an OpenShell sandbox
        resp2 = client_with_openshell.post(
            "/api/v1/sandboxes",
            json={
                "workspace_id": "ws1",
                "channel_id": "ch1",
                "thread_ts": "2.0",
                "backend": "openshell",
            },
        )
        assert resp2.status_code == 201

        # Neither is assigned to a pipeline, so cleanup should destroy both
        cleanup_resp = client_with_openshell.post("/api/v1/sandboxes/cleanup-unassigned")
        assert cleanup_resp.status_code == 200
        data = cleanup_resp.json()
        assert data["destroyed"] == 2
        assert data["failed"] == 0
