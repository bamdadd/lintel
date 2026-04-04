"""Tests for proactive trigger routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.proactive_triggers_api.store import (
    InMemoryTriggerExecutionStore,
    TriggerExecution,
)

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


class TestCreateProactiveTrigger:
    def test_create_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/proactive-triggers",
            json={
                "name": "Auto-review on PR",
                "event_pattern": "pr_opened",
                "agent_definition_id": "reviewer-agent",
                "project_id": "proj-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Auto-review on PR"
        assert data["event_pattern"] == "pr_opened"
        assert data["enabled"] is True

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "trigger_id": "dup-1",
            "name": "Dup",
            "event_pattern": "commit_pushed",
            "agent_definition_id": "agent-1",
            "project_id": "proj-1",
        }
        client.post("/api/v1/proactive-triggers", json=body)
        resp = client.post("/api/v1/proactive-triggers", json=body)
        assert resp.status_code == 409


class TestListProactiveTriggers:
    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/proactive-triggers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/proactive-triggers",
            json={
                "name": "t1",
                "event_pattern": "pr_merged",
                "agent_definition_id": "a1",
                "project_id": "p1",
            },
        )
        resp = client.get("/api/v1/proactive-triggers")
        assert len(resp.json()) == 1

    def test_filter_by_project(self, client: TestClient) -> None:
        for pid in ("p1", "p2"):
            client.post(
                "/api/v1/proactive-triggers",
                json={
                    "name": f"t-{pid}",
                    "event_pattern": "schedule",
                    "agent_definition_id": "a1",
                    "project_id": pid,
                },
            )
        resp = client.get("/api/v1/proactive-triggers", params={"project_id": "p1"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["project_id"] == "p1"


class TestGetProactiveTrigger:
    def test_get_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/proactive-triggers",
            json={
                "trigger_id": "t-1",
                "name": "test",
                "event_pattern": "pr_opened",
                "agent_definition_id": "a1",
                "project_id": "p1",
            },
        )
        resp = client.get("/api/v1/proactive-triggers/t-1")
        assert resp.status_code == 200
        assert resp.json()["trigger_id"] == "t-1"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/proactive-triggers/nonexistent")
        assert resp.status_code == 404


class TestDeleteProactiveTrigger:
    def test_delete_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/proactive-triggers",
            json={
                "trigger_id": "del-1",
                "name": "to-delete",
                "event_pattern": "pipeline_failed",
                "agent_definition_id": "a1",
                "project_id": "p1",
            },
        )
        resp = client.delete("/api/v1/proactive-triggers/del-1")
        assert resp.status_code == 204
        resp = client.get("/api/v1/proactive-triggers/del-1")
        assert resp.status_code == 404

    def test_delete_missing_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/proactive-triggers/nonexistent")
        assert resp.status_code == 404


class TestTriggerHistory:
    def test_history_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/proactive-triggers/history")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_history_returns_executions(
        self,
        client: TestClient,
        execution_store: InMemoryTriggerExecutionStore,
    ) -> None:
        await execution_store.add(
            TriggerExecution(
                execution_id="exec-1",
                trigger_id="t-1",
                event_payload={"ref": "main"},
                status="completed",
            )
        )
        resp = client.get("/api/v1/proactive-triggers/history")
        assert len(resp.json()) == 1
        assert resp.json()[0]["execution_id"] == "exec-1"
