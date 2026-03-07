"""Tests for chat API routes."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from lintel.api.app import create_app
from lintel.contracts.types import ModelPolicy
from lintel.domain.chat_router import ChatRouterResult

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> "Generator[TestClient]":
    with TestClient(create_app()) as c:
        # Replace the chat_router with a mock so tests don't hit Ollama
        mock_router = AsyncMock()
        mock_router.classify.return_value = ChatRouterResult(
            action="chat_reply",
            reply="[stub] mocked response",
        )
        mock_router.reply.return_value = "[stub] mocked response"
        c.app.state.chat_router = mock_router
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

    def test_list_conversations_filter_by_user(self, client: TestClient) -> None:
        _create_conversation(client, user_id="alice")
        _create_conversation(client, user_id="bob")

        resp = client.get("/api/v1/chat/conversations", params={"user_id": "alice"})
        assert resp.status_code == 200
        results = resp.json()
        assert len(results) == 1
        assert results[0]["user_id"] == "alice"

    def test_list_conversations_filter_by_project(self, client: TestClient) -> None:
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

    def test_get_conversation_not_found(self, client: TestClient) -> None:
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
        resp = client.delete("/api/v1/chat/conversations/nonexistent")
        assert resp.status_code == 404

    def test_create_conversation_with_model_id(self, client: TestClient) -> None:
        """Conversation stores the selected model_id."""
        resp = client.post(
            "/api/v1/chat/conversations",
            json={"user_id": "u1", "message": "hi", "model_id": "my-model"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["model_id"] == "my-model"

    def test_create_conversation_model_id_defaults_to_none(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/chat/conversations",
            json={"user_id": "u1", "message": "hi"},
        )
        assert resp.status_code == 201
        assert resp.json()["model_id"] is None


class TestChatModelResolution:
    """Tests that chat uses configured models instead of hardcoded ones."""

    @pytest.fixture()
    def client_with_model(self) -> "Generator[TestClient]":
        with TestClient(create_app()) as c:
            mock_router = AsyncMock()
            mock_router.classify.return_value = ChatRouterResult(
                action="chat_reply",
                reply="mocked",
            )
            mock_router.reply.return_value = "mocked reply"
            c.app.state.chat_router = mock_router
            yield c

    def _setup_model(self, client: TestClient) -> str:
        """Create a provider and model, return model_id."""
        # Create provider
        client.post(
            "/api/v1/ai-providers",
            json={
                "provider_id": "prov-test",
                "provider_type": "ollama",
                "name": "Test Ollama",
                "api_base": "http://localhost:11434",
            },
        )
        # Create model
        client.post(
            "/api/v1/models",
            json={
                "model_id": "test-model",
                "provider_id": "prov-test",
                "name": "Test Model",
                "model_name": "llama3.2:3b",
                "max_tokens": 2048,
                "temperature": 0.5,
            },
        )
        return "test-model"

    def test_chat_passes_model_policy_to_classify(
        self,
        client_with_model: TestClient,
    ) -> None:
        model_id = self._setup_model(client_with_model)
        client_with_model.post(
            "/api/v1/chat/conversations",
            json={"user_id": "u1", "message": "hello", "model_id": model_id},
        )
        mock_router = client_with_model.app.state.chat_router
        classify_call = mock_router.classify.call_args
        assert classify_call is not None
        policy = classify_call.kwargs.get("model_policy")
        assert policy is not None
        assert isinstance(policy, ModelPolicy)
        assert policy.provider == "ollama"
        assert policy.model_name == "llama3.2:3b"
        assert policy.max_tokens == 2048
        assert policy.temperature == 0.5
        assert classify_call.kwargs.get("api_base") == "http://localhost:11434"

    def test_chat_passes_model_policy_to_reply(
        self,
        client_with_model: TestClient,
    ) -> None:
        model_id = self._setup_model(client_with_model)
        client_with_model.post(
            "/api/v1/chat/conversations",
            json={"user_id": "u1", "message": "hello", "model_id": model_id},
        )
        mock_router = client_with_model.app.state.chat_router
        reply_call = mock_router.reply.call_args
        assert reply_call is not None
        policy = reply_call.kwargs.get("model_policy")
        assert policy is not None
        assert policy.provider == "ollama"
        assert policy.model_name == "llama3.2:3b"

    def test_send_message_inherits_conversation_model(
        self,
        client_with_model: TestClient,
    ) -> None:
        model_id = self._setup_model(client_with_model)
        resp = client_with_model.post(
            "/api/v1/chat/conversations",
            json={"user_id": "u1", "message": "hi", "model_id": model_id},
        )
        conv_id = resp.json()["conversation_id"]

        # Reset mock to check the follow-up call
        mock_router = client_with_model.app.state.chat_router
        mock_router.classify.reset_mock()
        mock_router.reply.reset_mock()

        client_with_model.post(
            f"/api/v1/chat/conversations/{conv_id}/messages",
            json={"user_id": "u1", "message": "follow-up"},
        )
        classify_call = mock_router.classify.call_args
        policy = classify_call.kwargs.get("model_policy")
        assert policy is not None
        assert policy.model_name == "llama3.2:3b"

    def test_no_model_passes_none_policy(self, client_with_model: TestClient) -> None:
        client_with_model.post(
            "/api/v1/chat/conversations",
            json={"user_id": "u1", "message": "hello"},
        )
        mock_router = client_with_model.app.state.chat_router
        classify_call = mock_router.classify.call_args
        assert classify_call.kwargs.get("model_policy") is None
