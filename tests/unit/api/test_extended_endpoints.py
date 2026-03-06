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
    "agent_role": "coder",
    "repo_url": "https://github.com/org/repo",
    "base_sha": "abc123",
    "commands": ["make test"],
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
    with TestClient(create_app()) as c:
        yield c


class TestAgentPolicies:
    def test_list_policies(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agents/policies")
        assert resp.status_code == 200
        data = resp.json()
        for role in ("planner", "coder", "reviewer", "pm", "designer", "summarizer"):
            assert role in data

    def test_get_policy(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agents/policies/planner")
        assert resp.status_code == 200
        data = resp.json()
        assert "role" in data
        assert "provider" in data

    def test_update_policy(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/agents/policies/planner",
            json={
                "provider": "openai",
                "model_name": "gpt-4o",
                "max_tokens": 8192,
                "temperature": 0.5,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["provider"] == "openai"
        assert data["model_name"] == "gpt-4o"

    def test_update_invalid_role(self, client: TestClient) -> None:
        resp = client.put(
            "/api/v1/agents/policies/invalid",
            json={
                "provider": "openai",
                "model_name": "gpt-4o",
            },
        )
        assert resp.status_code == 404

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
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/sandboxes")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_create_and_list(self, client: TestClient) -> None:
        client.post("/api/v1/sandboxes", json=SANDBOX_BODY)
        resp = client.get("/api/v1/sandboxes")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

    def test_get_sandbox(self, client: TestClient) -> None:
        post_resp = client.post("/api/v1/sandboxes", json=SANDBOX_BODY)
        sandbox_id = str(post_resp.json()["correlation_id"])
        resp = client.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 200

    def test_destroy_sandbox(self, client: TestClient) -> None:
        post_resp = client.post("/api/v1/sandboxes", json=SANDBOX_BODY)
        sandbox_id = str(post_resp.json()["correlation_id"])
        resp = client.delete(f"/api/v1/sandboxes/{sandbox_id}")
        assert resp.status_code == 204
        get_resp = client.get(f"/api/v1/sandboxes/{sandbox_id}")
        assert get_resp.json()["status"] == "destroyed"

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
