"""Tests for agent definitions API routes."""

from typing import TYPE_CHECKING

from fastapi.testclient import TestClient
from lintel.api.app import create_app
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        yield c


def _agent_payload(
    agent_id: str = "custom-agent-1",
    name: str = "Custom Agent",
) -> dict:
    return {
        "agent_id": agent_id,
        "name": name,
        "description": "A test agent",
        "system_prompt": "You are helpful.",
        "allowed_skills": [],
        "role": "coder",
    }


def _create_definition(client: TestClient, **overrides: str) -> dict:
    payload = _agent_payload(**overrides)
    resp = client.post("/api/v1/agents/definitions", json=payload)
    return resp.json()


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

    def test_list_definitions_has_builtins(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agents/definitions")
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) > 0
        ids = {d["agent_id"] for d in items}
        assert "agent_coder" in ids
        assert "agent_reviewer" in ids
        assert "agent_architect" in ids

    def test_list_definitions_after_create(self, client: TestClient) -> None:
        resp_before = client.get("/api/v1/agents/definitions")
        count_before = len(resp_before.json())
        _create_definition(client, agent_id="a1", name="A1")
        _create_definition(client, agent_id="a2", name="A2")

        resp = client.get("/api/v1/agents/definitions")
        assert resp.status_code == 200
        assert len(resp.json()) == count_before + 2

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
