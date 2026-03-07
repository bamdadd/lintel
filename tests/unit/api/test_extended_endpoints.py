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


@pytest.fixture()
def client() -> Generator[TestClient]:
    from tests.unit.api.test_sandboxes import DummySandboxManager

    app = create_app()
    with TestClient(app) as c:
        app.state.sandbox_manager = DummySandboxManager()
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
