"""Tests for agent definitions API routes and agent endpoints."""

from fastapi.testclient import TestClient


def _agent_payload(
    agent_id: str = "custom-agent-1",
    name: str = "Custom Agent",
) -> dict:  # type: ignore[type-arg]
    return {
        "agent_id": agent_id,
        "name": name,
        "description": "A test agent",
        "system_prompt": "You are helpful.",
        "allowed_skills": [],
        "role": "coder",
    }


def _create_definition(client: TestClient, **overrides: str) -> dict:  # type: ignore[type-arg]
    payload = _agent_payload(**overrides)
    resp = client.post("/api/v1/agents/definitions", json=payload)
    return resp.json()


class TestAgentAPI:
    def test_list_agent_roles(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agents/roles")
        assert resp.status_code == 200
        roles = resp.json()
        assert isinstance(roles, list)
        for expected in ("planner", "coder", "reviewer", "pm", "designer", "summarizer"):
            assert expected in roles

    def test_schedule_agent_step(self, client: TestClient) -> None:
        body = {
            "workspace_id": "W1",
            "channel_id": "C1",
            "thread_ts": "1234.5678",
            "agent_role": "coder",
            "step_name": "implement",
            "context": {"key": "value"},
        }
        resp = client.post("/api/v1/agents/steps", json=body)
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_role"] == "coder"
        assert data["step_name"] == "implement"
        assert data["thread_ref"] == {
            "workspace_id": "W1",
            "channel_id": "C1",
            "thread_ts": "1234.5678",
        }
        assert data["context"] == {"key": "value"}


class TestAgentDefinitions:
    def test_create_agent_definition(self, client: TestClient) -> None:
        payload = _agent_payload()
        resp = client.post("/api/v1/agents/definitions", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["agent_id"] == "custom-agent-1"
        assert data["name"] == "Custom Agent"

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        payload = _agent_payload()
        client.post("/api/v1/agents/definitions", json=payload)
        resp = client.post("/api/v1/agents/definitions", json=payload)
        assert resp.status_code == 409

    def test_list_definitions_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agents/definitions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_definitions_after_create(self, client: TestClient) -> None:
        _create_definition(client, agent_id="a1", name="A1")
        _create_definition(client, agent_id="a2", name="A2")
        resp = client.get("/api/v1/agents/definitions")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_get_definition(self, client: TestClient) -> None:
        _create_definition(client, agent_id="lookup-me")
        resp = client.get("/api/v1/agents/definitions/lookup-me")
        assert resp.status_code == 200
        assert resp.json()["agent_id"] == "lookup-me"

    def test_get_definition_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agents/definitions/nope")
        assert resp.status_code == 404

    def test_update_definition(self, client: TestClient) -> None:
        _create_definition(client, agent_id="upd-1")
        resp = client.patch(
            "/api/v1/agents/definitions/upd-1",
            json={"name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated Name"

    def test_update_not_found(self, client: TestClient) -> None:
        resp = client.patch(
            "/api/v1/agents/definitions/nope",
            json={"name": "X"},
        )
        assert resp.status_code == 404

    def test_delete_definition(self, client: TestClient) -> None:
        _create_definition(client, agent_id="del-me")
        resp = client.delete("/api/v1/agents/definitions/del-me")
        assert resp.status_code == 204
        resp = client.get("/api/v1/agents/definitions/del-me")
        assert resp.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/agents/definitions/nope")
        assert resp.status_code == 404
