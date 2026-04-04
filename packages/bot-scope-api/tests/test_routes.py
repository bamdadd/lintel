"""Tests for bot-scope API."""

from fastapi.testclient import TestClient

from lintel.bot_scope_api.routes import bot_store_provider
from lintel.domain.types import Bot


class TestBotScopeAPI:
    def test_create_bot_scope_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/bot-scopes",
            json={
                "bot_id": "bot-1",
                "resource_type": "project",
                "resource_id": "proj-1",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bot_id"] == "bot-1"
        assert data["resource_type"] == "project"
        assert data["resource_id"] == "proj-1"

    def test_get_bot_scopes(self, client: TestClient) -> None:
        client.post(
            "/api/v1/bot-scopes",
            json={
                "bot_id": "bot-2",
                "resource_type": "workflow",
                "resource_id": "wf-1",
            },
        )
        resp = client.get("/api/v1/bot-scopes/bot-2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_id"] == "bot-2"
        assert len(data["scopes"]) == 1
        assert data["scopes"][0]["resource_type"] == "workflow"

    def test_get_bot_scopes_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/v1/bot-scopes/nonexistent")
        assert resp.status_code == 404

    def test_check_scope_allowed(self, client: TestClient) -> None:
        client.post(
            "/api/v1/bot-scopes",
            json={
                "bot_id": "bot-3",
                "resource_type": "agent",
                "resource_id": "agent-1",
            },
        )
        resp = client.post(
            "/api/v1/bot-scopes/check",
            json={
                "bot_id": "bot-3",
                "resource_type": "agent",
                "resource_id": "agent-1",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "allowed"

    def test_check_scope_denied(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/bot-scopes/check",
            json={
                "bot_id": "bot-4",
                "resource_type": "project",
                "resource_id": "proj-99",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "denied"

    def test_multiple_scopes_per_bot(self, client: TestClient) -> None:
        for rid in ["proj-1", "proj-2"]:
            client.post(
                "/api/v1/bot-scopes",
                json={
                    "bot_id": "bot-5",
                    "resource_type": "project",
                    "resource_id": rid,
                },
            )
        resp = client.get("/api/v1/bot-scopes/bot-5")
        assert len(resp.json()["scopes"]) == 2

    def test_check_scope_wildcard_allowed(self, client: TestClient) -> None:
        client.post(
            "/api/v1/bot-scopes",
            json={
                "bot_id": "bot-w",
                "resource_type": "project",
                "resource_id": "*",
            },
        )
        resp = client.post(
            "/api/v1/bot-scopes/check",
            json={
                "bot_id": "bot-w",
                "resource_type": "project",
                "resource_id": "any-proj",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "allowed"


class TestResolveAccessAPI:
    async def _register_bot(self, client: TestClient, bot_id: str = "bot-r") -> None:
        store = bot_store_provider.get()
        await store.add(Bot(bot_id=bot_id, name=f"Bot {bot_id}"))

    def test_resolve_unknown_token(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/bot-scopes/resolve",
            json={"token": "unknown"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False
        assert "Unknown bot token" in data["deny_reason"]

    async def test_resolve_allowed(self, client: TestClient) -> None:
        await self._register_bot(client, "bot-r")
        client.post(
            "/api/v1/bot-scopes",
            json={"bot_id": "bot-r", "resource_type": "project", "resource_id": "proj-1"},
        )
        resp = client.post(
            "/api/v1/bot-scopes/resolve",
            json={"token": "bot-r", "project_id": "proj-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True
        assert data["bot_id"] == "bot-r"

    async def test_resolve_denied(self, client: TestClient) -> None:
        await self._register_bot(client, "bot-d")
        resp = client.post(
            "/api/v1/bot-scopes/resolve",
            json={"token": "bot-d", "project_id": "proj-x"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False
        assert "project:proj-x" in data["deny_reason"]

    async def test_resolve_multi_dimension(self, client: TestClient) -> None:
        await self._register_bot(client, "bot-m")
        client.post(
            "/api/v1/bot-scopes",
            json={"bot_id": "bot-m", "resource_type": "project", "resource_id": "*"},
        )
        client.post(
            "/api/v1/bot-scopes",
            json={"bot_id": "bot-m", "resource_type": "workflow", "resource_id": "wf-1"},
        )
        resp = client.post(
            "/api/v1/bot-scopes/resolve",
            json={
                "token": "bot-m",
                "project_id": "any-proj",
                "workflow_id": "wf-1",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True
        assert len(data["checks"]) == 2
