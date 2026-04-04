"""Tests for bot scope enforcement in the chat API flow."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from lintel.bot_scope_api.routes import bot_scope_store_provider, bot_store_provider
from lintel.bot_scope_api.types import ALL_RESOURCES, BotScope, ScopeResource
from lintel.domain.types import Bot

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from lintel.bot_scope_api.store import InMemoryBotScopeStore
    from lintel.bots_api.store import InMemoryBotStore


def _seed_bot(client: TestClient, bot_id: str = "bot-1") -> None:
    """Seed a bot into the bot store."""
    bot_store: InMemoryBotStore = bot_store_provider.get()  # type: ignore[assignment]
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(bot_store.add(Bot(bot_id=bot_id, name=f"Bot {bot_id}")))
    finally:
        loop.close()


def _seed_scope(
    resource_type: ScopeResource,
    resource_id: str,
    bot_id: str = "bot-1",
) -> None:
    """Seed a bot scope into the scope store."""
    scope_store: InMemoryBotScopeStore = bot_scope_store_provider.get()  # type: ignore[assignment]
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(
            scope_store.add(
                BotScope(bot_id=bot_id, resource_type=resource_type, resource_id=resource_id)
            )
        )
    finally:
        loop.close()


def _create_project(client: TestClient, project_id: str = "proj-1") -> None:
    """Create a project for the test."""
    resp = client.post(
        "/api/v1/projects",
        json={"project_id": project_id, "name": f"Project {project_id}"},
    )
    assert resp.status_code in (200, 201)


class TestBotScopeEnforcement:
    def test_conversation_stores_bot_id(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/chat/conversations",
            json={"user_id": "user-1", "bot_id": "bot-1"},
        )
        assert resp.status_code == 201
        conv_id = resp.json()["conversation_id"]

        conv = client.get(f"/api/v1/chat/conversations/{conv_id}")
        assert conv.status_code == 200
        assert conv.json().get("bot_id") == "bot-1"

    def test_workflow_blocked_when_bot_has_no_scope(self, client: TestClient) -> None:
        """A bot without scopes should be blocked from dispatching workflows."""
        _seed_bot(client, "bot-blocked")
        _create_project(client, "proj-1")

        # Create conversation with project and bot
        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user-1",
                "bot_id": "bot-blocked",
                "project_id": "proj-1",
                "message": "build a login page with oauth support for the frontend",
            },
        )
        assert resp.status_code == 201
        conv = resp.json()
        messages = conv.get("messages", [])
        # The last agent message should contain the scope denial
        agent_msgs = [m for m in messages if m.get("role") == "agent"]
        assert any("does not have access" in m.get("content", "") for m in agent_msgs)

    def test_workflow_allowed_with_wildcard_scope(self, client: TestClient) -> None:
        """A bot with wildcard scopes should be allowed."""
        _seed_bot(client, "bot-all")
        _seed_scope(ScopeResource.PROJECT, ALL_RESOURCES, "bot-all")
        _seed_scope(ScopeResource.WORKFLOW, ALL_RESOURCES, "bot-all")
        _create_project(client, "proj-2")

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user-1",
                "bot_id": "bot-all",
                "project_id": "proj-2",
                "message": "build a login page with oauth support for the frontend",
            },
        )
        assert resp.status_code == 201
        conv = resp.json()
        messages = conv.get("messages", [])
        agent_msgs = [m for m in messages if m.get("role") == "agent"]
        # Should NOT contain scope denial
        assert not any("does not have access" in m.get("content", "") for m in agent_msgs)

    def test_no_bot_id_bypasses_scope_check(self, client: TestClient) -> None:
        """Conversations without a bot_id should not be scope-checked."""
        _create_project(client, "proj-3")

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user-1",
                "project_id": "proj-3",
                "message": "build a login page with oauth support for the frontend",
            },
        )
        assert resp.status_code == 201
        conv = resp.json()
        messages = conv.get("messages", [])
        agent_msgs = [m for m in messages if m.get("role") == "agent"]
        assert not any("does not have access" in m.get("content", "") for m in agent_msgs)

    def test_bot_with_specific_project_scope(self, client: TestClient) -> None:
        """A bot scoped to proj-1 should be denied access to proj-2."""
        _seed_bot(client, "bot-specific")
        _seed_scope(ScopeResource.PROJECT, "proj-1", "bot-specific")
        _seed_scope(ScopeResource.WORKFLOW, ALL_RESOURCES, "bot-specific")
        _create_project(client, "proj-wrong")

        resp = client.post(
            "/api/v1/chat/conversations",
            json={
                "user_id": "user-1",
                "bot_id": "bot-specific",
                "project_id": "proj-wrong",
                "message": "build a login page with oauth support for the frontend",
            },
        )
        assert resp.status_code == 201
        conv = resp.json()
        messages = conv.get("messages", [])
        agent_msgs = [m for m in messages if m.get("role") == "agent"]
        assert any("does not have access" in m.get("content", "") for m in agent_msgs)
