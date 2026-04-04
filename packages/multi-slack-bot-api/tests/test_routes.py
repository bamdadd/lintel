"""Tests for multi-slack-bot API."""

from fastapi.testclient import TestClient


class TestSlackBotsAPI:
    def test_create_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/slack-bots",
            json={
                "bot_id": "bot-1",
                "name": "My Bot",
                "workspace_id": "ws-1",
                "bot_token": "xoxb-test",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bot_id"] == "bot-1"
        assert data["name"] == "My Bot"
        assert data["enabled"] is True

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "bot_id": "bot-dup",
            "name": "Dup",
            "workspace_id": "ws-1",
            "bot_token": "xoxb-test",
        }
        client.post("/api/v1/slack-bots", json=body)
        resp = client.post("/api/v1/slack-bots", json=body)
        assert resp.status_code == 409

    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack-bots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={"bot_id": "bot-2", "name": "B2", "workspace_id": "ws-1", "bot_token": "t"},
        )
        resp = client.get("/api/v1/slack-bots")
        assert len(resp.json()) == 1

    def test_list_filter_by_workspace_id(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={"bot_id": "b1", "name": "B1", "workspace_id": "ws-1", "bot_token": "t"},
        )
        client.post(
            "/api/v1/slack-bots",
            json={"bot_id": "b2", "name": "B2", "workspace_id": "ws-2", "bot_token": "t"},
        )
        resp = client.get("/api/v1/slack-bots", params={"workspace_id": "ws-1"})
        assert len(resp.json()) == 1
        assert resp.json()[0]["workspace_id"] == "ws-1"

    def test_get_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={"bot_id": "bot-3", "name": "B3", "workspace_id": "ws-1", "bot_token": "t"},
        )
        resp = client.get("/api/v1/slack-bots/bot-3")
        assert resp.status_code == 200
        assert resp.json()["bot_id"] == "bot-3"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/slack-bots/nonexistent")
        assert resp.status_code == 404

    def test_patch_updates_fields(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={"bot_id": "bot-4", "name": "Old", "workspace_id": "ws-1", "bot_token": "t"},
        )
        resp = client.patch(
            "/api/v1/slack-bots/bot-4",
            json={"name": "New", "enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"
        assert resp.json()["enabled"] is False

    def test_patch_missing_returns_404(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/slack-bots/missing", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_existing_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/slack-bots",
            json={"bot_id": "bot-5", "name": "B5", "workspace_id": "ws-1", "bot_token": "t"},
        )
        resp = client.delete("/api/v1/slack-bots/bot-5")
        assert resp.status_code == 204
        assert client.get("/api/v1/slack-bots/bot-5").status_code == 404

    def test_delete_missing_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/slack-bots/nonexistent")
        assert resp.status_code == 404
