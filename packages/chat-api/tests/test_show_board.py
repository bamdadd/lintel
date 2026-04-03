"""Tests for the show_board intent handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
    work_item_id: str = "wi-1",
    status: str = "open",
    title: str = "Add dark mode",
    work_type: str = "feature",
    project_id: str = "proj-1",
) -> dict[str, Any]:
    resp = client.post(
        "/api/v1/work-items",
        json={
            "work_item_id": work_item_id,
            "title": title,
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
    assert resp.status_code == 201
    return resp.json()["conversation_id"]


def _send(client: TestClient, conv_id: str, message: str) -> dict[str, Any]:
    resp = client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"user_id": "test-user", "message": message},
    )
    assert resp.status_code == 201
    return resp.json()


def _agent_messages(client: TestClient, conv_id: str) -> list[str]:
    msgs = client.get(f"/api/v1/chat/conversations/{conv_id}").json()["messages"]
    return [m["content"] for m in msgs if m["role"] == "agent"]


class TestShowBoardViaChat:
    def test_show_board_with_items(self, client: TestClient) -> None:
        _create_project(client)
        _create_work_item(client, work_item_id="wi-1", status="open", title="Add dark mode")
        _create_work_item(client, work_item_id="wi-2", status="in_progress", title="Fix login bug")
        conv_id = _create_conversation(client)

        _send(client, conv_id, "show board")

        replies = _agent_messages(client, conv_id)
        board_reply = replies[-1]
        assert "Open" in board_reply
        assert "In Progress" in board_reply
        assert "dark mode" in board_reply.lower() or "Add dark mode" in board_reply

    def test_show_board_empty(self, client: TestClient) -> None:
        _create_project(client)
        conv_id = _create_conversation(client)

        _send(client, conv_id, "show the board")

        replies = _agent_messages(client, conv_id)
        board_reply = replies[-1]
        assert "empty" in board_reply.lower() or "no work items" in board_reply.lower()

    def test_kanban_keyword_triggers_board(self, client: TestClient) -> None:
        _create_project(client)
        _create_work_item(client, work_item_id="wi-1", status="open", title="Setup CI")
        conv_id = _create_conversation(client)

        _send(client, conv_id, "kanban")

        replies = _agent_messages(client, conv_id)
        assert any("Setup CI" in r for r in replies)

    def test_whats_in_progress_triggers_board(self, client: TestClient) -> None:
        _create_project(client)
        _create_work_item(client, work_item_id="wi-1", status="in_progress", title="Refactor auth")
        conv_id = _create_conversation(client)

        _send(client, conv_id, "what's in progress")

        replies = _agent_messages(client, conv_id)
        assert any("Refactor auth" in r for r in replies)
