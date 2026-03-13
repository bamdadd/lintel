"""Tests for the agent API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient
from lintel.api.app import create_app


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


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
