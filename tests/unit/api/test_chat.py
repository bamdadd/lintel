"""Tests for chat API routes."""

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


def _create_conversation(
    client: TestClient,
    *,
    user_id: str = "u1",
    message: str = "hello",
    project_id: str | None = None,
) -> dict:
    payload: dict = {
        "user_id": user_id,
        "message": message,
    }
    if project_id is not None:
        payload["project_id"] = project_id
    resp = client.post("/api/v1/chat/conversations", json=payload)
    return resp.json()


class TestChatConversations:
    def test_create_conversation(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/chat/conversations",
            json={"user_id": "u1", "message": "hi"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "conversation_id" in data
        assert len(data["messages"]) == 2
        assert data["messages"][0]["role"] == "user"
        assert data["messages"][0]["content"] == "hi"
        assert data["messages"][1]["role"] == "agent"
        assert "[stub]" in data["messages"][1]["content"]

    def test_list_conversations_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/chat/conversations")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_conversations_filter_by_user(
        self, client: TestClient
    ) -> None:
        _create_conversation(client, user_id="alice")
        _create_conversation(client, user_id="bob")

        resp = client.get(
            "/api/v1/chat/conversations", params={"user_id": "alice"}
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["user_id"] == "alice"

    def test_list_conversations_filter_by_project(
        self, client: TestClient
    ) -> None:
        _create_conversation(client, project_id="proj-1")
        _create_conversation(client, project_id="proj-2")

        resp = client.get(
            "/api/v1/chat/conversations",
            params={"project_id": "proj-1"},
        )
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["project_id"] == "proj-1"

    def test_get_conversation(self, client: TestClient) -> None:
        conv = _create_conversation(client)
        cid = conv["conversation_id"]

        resp = client.get(f"/api/v1/chat/conversations/{cid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["conversation_id"] == cid
        assert len(data["messages"]) == 2

    def test_get_conversation_not_found(
        self, client: TestClient
    ) -> None:
        resp = client.get("/api/v1/chat/conversations/nonexistent")
        assert resp.status_code == 404

    def test_send_message(self, client: TestClient) -> None:
        conv = _create_conversation(client)
        cid = conv["conversation_id"]

        resp = client.post(
            f"/api/v1/chat/conversations/{cid}/messages",
            json={"user_id": "u1", "message": "follow-up"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "follow-up"
        assert data["role"] == "user"

    def test_send_message_not_found(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/chat/conversations/nonexistent/messages",
            json={"user_id": "u1", "message": "nope"},
        )
        assert resp.status_code == 404

    def test_delete_conversation(self, client: TestClient) -> None:
        conv = _create_conversation(client)
        cid = conv["conversation_id"]

        resp = client.delete(f"/api/v1/chat/conversations/{cid}")
        assert resp.status_code == 204

        resp = client.get(f"/api/v1/chat/conversations/{cid}")
        assert resp.status_code == 404

    def test_delete_not_found(self, client: TestClient) -> None:
        resp = client.delete(
            "/api/v1/chat/conversations/nonexistent"
        )
        assert resp.status_code == 404
