"""Tests for extended endpoints across multiple route files."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient

from lintel.api.app import create_app

SANDBOX_BODY: dict[str, object] = {
    "workspace_id": "W1",
    "channel_id": "C1",
    "thread_ts": "123.456",
}

SKILL_BODY: dict[str, object] = {
    "skill_id": "sk1",
    "version": "1.0.0",
    "name": "test-skill",
    "input_schema": {},
    "output_schema": {},
    "execution_mode": "inline",
}

REVEAL_BODY: dict[str, object] = {
    "workspace_id": "W1",
    "channel_id": "C1",
    "thread_ts": "123.456",
    "placeholder": "<PII:email:abc>",
    "requester_id": "U1",
    "reason": "debugging",
}


class _StubSandboxManager:
    """Sandbox manager stub that tracks created sandboxes for extended endpoint tests."""

    def __init__(self) -> None:
        self._sandboxes: set[str] = set()

    async def create(self, config: object, thread_ref: object) -> str:
        from uuid import uuid4

        sid = str(uuid4())
        self._sandboxes.add(sid)
        return sid

    async def execute(self, sandbox_id: str, job: object) -> object:
        from lintel.contracts.errors import SandboxNotFoundError
        from lintel.contracts.types import SandboxResult

        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return SandboxResult(exit_code=0, stdout="ok\n")

    async def destroy(self, sandbox_id: str) -> None:
        self._sandboxes.discard(sandbox_id)

    async def get_status(self, sandbox_id: str) -> object:
        from lintel.contracts.errors import SandboxNotFoundError
        from lintel.contracts.types import SandboxStatus

        if sandbox_id not in self._sandboxes:
            raise SandboxNotFoundError(sandbox_id)
        return SandboxStatus.RUNNING

    async def read_file(self, sandbox_id: str, path: str) -> str:
        return ""

    async def write_file(self, sandbox_id: str, path: str, content: str) -> None:
        pass

    async def list_files(self, sandbox_id: str, path: str = "/workspace") -> list[str]:
        return []

    async def collect_artifacts(
        self,
        sandbox_id: str,
        workdir: str = "/workspace",
    ) -> dict[str, object]:
        return {"type": "diff", "content": "some diff"}

    async def reconnect_network(self, sandbox_id: str) -> None:
        pass

    async def disconnect_network(self, sandbox_id: str) -> None:
        pass


@pytest.fixture()
def client() -> Generator[TestClient]:
    app = create_app()
    with TestClient(app) as c:
        app.state.sandbox_manager = _StubSandboxManager()
        yield c


class TestAgentEndpoints:
    def test_test_prompt(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/agents/test-prompt",
            json={
                "agent_role": "planner",
                "messages": [{"role": "user", "content": "hello"}],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "dry-run" in data["response"]["content"]


class TestSandboxes:
    def test_create_sandbox(self, client: TestClient) -> None:
        resp = client.post("/api/v1/sandboxes", json=SANDBOX_BODY)
        assert resp.status_code == 201
        assert "sandbox_id" in resp.json()

    def test_get_sandbox(self, client: TestClient) -> None:
        post_resp = client.post("/api/v1/sandboxes", json=SANDBOX_BODY)
        sandbox_id = post_resp.json()["sandbox_id"]
        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "running"

    def test_destroy_sandbox(self, client: TestClient) -> None:
        post_resp = client.post("/api/v1/sandboxes", json=SANDBOX_BODY)
        sandbox_id = post_resp.json()["sandbox_id"]
        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 204

    def test_get_nonexistent(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandboxes/nonexistent")
        assert resp.status_code == 404


class TestSkills:
    def test_get_skill_detail(self, client: TestClient) -> None:
        client.post("/api/v1/skills", json=SKILL_BODY)
        resp = client.get("/api/v1/skills/sk1")
        assert resp.status_code == 200
        assert resp.json()["skill_id"] == "sk1"

    def test_get_nonexistent_skill(self, client: TestClient) -> None:
        resp = client.get("/api/v1/skills/nonexistent")
        assert resp.status_code == 404


class TestPII:
    def test_vault_log_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/pii/vault/log")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_reveal_then_log(self, client: TestClient) -> None:
        client.post("/api/v1/pii/reveal", json=REVEAL_BODY)
        resp = client.get("/api/v1/pii/vault/log")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_pii_stats(self, client: TestClient) -> None:
        resp = client.get("/api/v1/pii/stats")
        assert resp.status_code == 200
        assert "total_reveals" in resp.json()


class TestEvents:
    def test_list_event_types(self, client: TestClient) -> None:
        resp = client.get("/api/v1/events/types")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert "WorkflowStarted" in data
