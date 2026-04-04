"""Tests for bot-scope API."""

from fastapi.testclient import TestClient

from lintel.bot_scope_api.routes import bot_scope_resolver_provider


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

    def test_wildcard_scope_allows_any_resource(self, client: TestClient) -> None:
        client.post(
            "/api/v1/bot-scopes",
            json={
                "bot_id": "bot-6",
                "resource_type": "project",
                "resource_id": "*",
            },
        )
        resp = client.post(
            "/api/v1/bot-scopes/check",
            json={
                "bot_id": "bot-6",
                "resource_type": "project",
                "resource_id": "any-project-id",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["decision"] == "allowed"


class TestResolveAccessEndpoint:
    def test_resolve_unmapped_connection(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/bot-scopes/resolve",
            json={"connection_id": "unknown", "project_id": "proj-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True
        assert data["bot_id"] == ""

    def test_resolve_mapped_allowed(self, client: TestClient) -> None:
        # Register scope
        client.post(
            "/api/v1/bot-scopes",
            json={"bot_id": "bot-r", "resource_type": "project", "resource_id": "proj-1"},
        )
        # Map connection to bot
        resolver = bot_scope_resolver_provider.get()
        resolver.register_connection("conn-r", "bot-r")

        resp = client.post(
            "/api/v1/bot-scopes/resolve",
            json={"connection_id": "conn-r", "project_id": "proj-1"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is True
        assert data["bot_id"] == "bot-r"

    def test_resolve_mapped_denied(self, client: TestClient) -> None:
        client.post(
            "/api/v1/bot-scopes",
            json={"bot_id": "bot-d", "resource_type": "project", "resource_id": "proj-1"},
        )
        resolver = bot_scope_resolver_provider.get()
        resolver.register_connection("conn-d", "bot-d")

        resp = client.post(
            "/api/v1/bot-scopes/resolve",
            json={"connection_id": "conn-d", "project_id": "proj-other"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["allowed"] is False
        assert data["bot_id"] == "bot-d"
        assert "proj-other" in data["reason"]
