"""Tests for bot-scope API."""

from fastapi.testclient import TestClient


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
