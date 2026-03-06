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
        return sandbox_id

    async def execute(self, sandbox_id: str, job: SandboxJob) -> SandboxResult:
        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
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

    async def collect_artifacts(self, sandbox_id: str) -> dict[str, Any]:
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
