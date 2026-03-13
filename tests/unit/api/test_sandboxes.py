"""Tests for the sandbox API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

import pytest

from lintel.contracts.errors import SandboxNotFoundError
from lintel.contracts.types import (
    SandboxConfig,
    SandboxJob,
    SandboxResult,
    SandboxStatus,
    ThreadRef,
)

if TYPE_CHECKING:
    from collections.abc import Generator

from fastapi.testclient import TestClient

from lintel.api.app import create_app


class DummySandboxManager:
    """In-memory sandbox manager for API tests."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, str]] = {}

    async def create(self, config: SandboxConfig, thread_ref: ThreadRef) -> str:
        sandbox_id = str(uuid4())
        self._sandboxes[sandbox_id] = {}
        self.last_config = config
        return sandbox_id

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        # Support cat commands for read_file via execute
        if job.command.startswith("cat "):
            path = job.command[4:].strip()
            content = self._sandboxes[sandbox_id].get(path, "")
            if not content:
                return SandboxResult(exit_code=1, stdout="", stderr=f"cat: {path}: No such file")
            return SandboxResult(exit_code=0, stdout=content)
        return SandboxResult(exit_code=0, stdout="ok\n")

    async def read_file(self, sandbox_id: str, path: str) -> str:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return self._sandboxes[sandbox_id].get(path, "")

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        self._sandboxes[sandbox_id][path] = content

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return [k for k in self._sandboxes[sandbox_id] if k.startswith(path)]

    async def get_status(self, sandbox_id: str) -> SandboxStatus:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return SandboxStatus.RUNNING

    async def collect_artifacts(
        self,
        sandbox_id: str,
        workdir: str = "/workspace",
    ) -> dict[str, Any]:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return {"type": "diff", "content": ""}

    async def destroy(self, sandbox_id: str) -> None:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        del self._sandboxes[sandbox_id]


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = create_app()
    with TestClient(app) as c:
        app.state.sandbox_manager = DummySandboxManager()
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
        manager: DummySandboxManager = client.app.state.sandbox_manager  # type: ignore[union-attr]
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

        manager: DummySandboxManager = client.app.state.sandbox_manager  # type: ignore[union-attr]
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

        manager: DummySandboxManager = client.app.state.sandbox_manager  # type: ignore[union-attr]
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
