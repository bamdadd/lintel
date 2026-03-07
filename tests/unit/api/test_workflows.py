"""Tests for the workflow API endpoints."""

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


class TestWorkflowAPI:
    def test_start_workflow(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workflows",
            json={
                "workspace_id": "W1",
                "channel_id": "C1",
                "thread_ts": "123.456",
                "workflow_type": "code_review",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "run_id" in data
        assert data["status"] == "started"

    def test_list_workflows_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflows")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_get_workflow_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/workflows/nonexistent")
        assert resp.status_code == 404

    def test_process_message(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/workflows/messages",
            json={
                "workspace_id": "W1",
                "channel_id": "C1",
                "thread_ts": "123.456",
                "raw_text": "Hello world",
                "sender_id": "U1",
                "sender_name": "alice",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["raw_text"] == "Hello world"
        assert data["sender_id"] == "U1"
        assert data["sender_name"] == "alice"
        assert data["thread_ref"]["workspace_id"] == "W1"
