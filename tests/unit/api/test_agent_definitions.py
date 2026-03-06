"""Tests for agent definitions API routes."""

from typing import TYPE_CHECKING

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app

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
        "model_policy": {
            "provider": "anthropic",
            "model_name": "claude-sonnet-4-20250514",
        },
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

    def test_list_definitions_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/agents/definitions")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_definitions(self, client: TestClient) -> None:
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
