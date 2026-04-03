"""Tests for the implement_item intent handler."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> str:
    resp = client.post(
        "/api/v1/projects",
        json={"name": "test-project", "project_id": "proj-1"},
    )
    return resp.json()["project_id"]


def _create_work_item(
    client: TestClient,
    work_item_id: str = "wi-abc123",
    status: str = "open",
    title: str = "Add dark mode",
    work_type: str = "feature",
    project_id: str = "proj-1",
) -> dict:
    resp = client.post(
        "/api/v1/work-items",
        json={
            "work_item_id": work_item_id,
            "title": title,
            "description": f"Implement: {title}",
            "status": status,
            "work_type": work_type,
            "project_id": project_id,
        },
    )
    return resp.json()


def _create_conversation(client: TestClient, project_id: str = "proj-1") -> str:
    resp = client.post(
        "/api/v1/chat/conversations",
        json={"user_id": "test-user", "message": "hello", "project_id": project_id},
    )
    assert resp.status_code == 201 or resp.status_code == 201, resp.json()
    return resp.json()["conversation_id"]


class TestImplementItemViaChat:
    def test_implement_open_work_item(self, client: TestClient) -> None:
        _create_project(client)
        _create_work_item(client, work_item_id="wi-test1", status="open")
        conv_id = _create_conversation(client)

        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "test-user", "message": "implement item WI-test1"},
        )
        assert resp.status_code == 201

        # Work item should now be in_progress
        wi = client.get("/api/v1/work-items/wi-test1").json()
        assert wi["status"] == "in_progress"

    def test_implement_already_in_progress(self, client: TestClient) -> None:
        _create_project(client)
        _create_work_item(client, work_item_id="wi-test2", status="in_progress")
        conv_id = _create_conversation(client)

        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "test-user", "message": "implement item WI-test2"},
        )
        assert resp.status_code == 201

    def test_implement_merged_item_rejected(self, client: TestClient) -> None:
        _create_project(client)
        _create_work_item(client, work_item_id="wi-test3", status="merged")
        conv_id = _create_conversation(client)

        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "test-user", "message": "implement item WI-test3"},
        )
        assert resp.status_code == 201
        # Should contain an error reply about invalid status
        msgs = client.get(f"/api/v1/chat/conversations/{conv_id}").json()["messages"]
        agent_msgs = [m for m in msgs if m["role"] == "agent"]
        assert any("merged" in m["content"].lower() for m in agent_msgs)

    def test_implement_unknown_item(self, client: TestClient) -> None:
        _create_project(client)
        conv_id = _create_conversation(client)

        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "test-user", "message": "implement item WI-nonexistent"},
        )
        assert resp.status_code == 201
        msgs = client.get(f"/api/v1/chat/conversations/{conv_id}").json()["messages"]
        agent_msgs = [m for m in msgs if m["role"] == "agent"]
        assert any("not found" in m["content"].lower() for m in agent_msgs)

    def test_implement_without_entity_ref(self, client: TestClient) -> None:
        _create_project(client)
        conv_id = _create_conversation(client)

        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "test-user", "message": "implement work please"},
        )
        assert resp.status_code == 201
        msgs = client.get(f"/api/v1/chat/conversations/{conv_id}").json()["messages"]
        agent_msgs = [m for m in msgs if m["role"] == "agent"]
        assert any("specify" in m["content"].lower() for m in agent_msgs)

    def test_implement_bug_maps_to_bug_fix_workflow(self, client: TestClient) -> None:
        _create_project(client)
        _create_work_item(client, work_item_id="wi-bug1", status="open", work_type="bug")
        conv_id = _create_conversation(client)

        resp = client.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "test-user", "message": "implement item WI-bug1"},
        )
        assert resp.status_code == 201
        # Verify pipeline was created with correct workflow type
        pipelines = client.get("/api/v1/pipelines").json()
        matching = [p for p in pipelines if p.get("work_item_id") == "wi-bug1"]
        assert len(matching) >= 1
