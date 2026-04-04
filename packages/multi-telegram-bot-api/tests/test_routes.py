"""Tests for multi-telegram-bot API."""

from fastapi.testclient import TestClient


class TestTelegramBotsAPI:
    def test_create_returns_201(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/telegram-bots",
            json={
                "bot_id": "bot-1",
                "name": "My TG Bot",
                "bot_token": "123456:ABC-DEF",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["bot_id"] == "bot-1"
        assert data["name"] == "My TG Bot"
        assert data["enabled"] is True

    def test_create_duplicate_returns_409(self, client: TestClient) -> None:
        body = {
            "bot_id": "bot-dup",
            "name": "Dup",
            "bot_token": "123456:ABC-DEF",
        }
        client.post("/api/v1/telegram-bots", json=body)
        resp = client.post("/api/v1/telegram-bots", json=body)
        assert resp.status_code == 409

    def test_list_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/telegram-bots")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_returns_created(self, client: TestClient) -> None:
        client.post(
            "/api/v1/telegram-bots",
            json={"bot_id": "bot-2", "name": "B2", "bot_token": "t"},
        )
        resp = client.get("/api/v1/telegram-bots")
        assert len(resp.json()) == 1

    def test_get_existing(self, client: TestClient) -> None:
        client.post(
            "/api/v1/telegram-bots",
            json={"bot_id": "bot-3", "name": "B3", "bot_token": "t"},
        )
        resp = client.get("/api/v1/telegram-bots/bot-3")
        assert resp.status_code == 200
        assert resp.json()["bot_id"] == "bot-3"

    def test_get_missing_returns_404(self, client: TestClient) -> None:
        resp = client.get("/api/v1/telegram-bots/nonexistent")
        assert resp.status_code == 404

    def test_patch_updates_fields(self, client: TestClient) -> None:
        client.post(
            "/api/v1/telegram-bots",
            json={"bot_id": "bot-4", "name": "Old", "bot_token": "t"},
        )
        resp = client.patch(
            "/api/v1/telegram-bots/bot-4",
            json={"name": "New", "enabled": False},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New"
        assert resp.json()["enabled"] is False

    def test_patch_missing_returns_404(self, client: TestClient) -> None:
        resp = client.patch("/api/v1/telegram-bots/missing", json={"name": "X"})
        assert resp.status_code == 404

    def test_delete_existing_returns_204(self, client: TestClient) -> None:
        client.post(
            "/api/v1/telegram-bots",
            json={"bot_id": "bot-5", "name": "B5", "bot_token": "t"},
        )
        resp = client.delete("/api/v1/telegram-bots/bot-5")
        assert resp.status_code == 204
        assert client.get("/api/v1/telegram-bots/bot-5").status_code == 404

    def test_delete_missing_returns_404(self, client: TestClient) -> None:
        resp = client.delete("/api/v1/telegram-bots/nonexistent")
        assert resp.status_code == 404

    def test_create_with_webhook_secret(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/telegram-bots",
            json={
                "bot_id": "bot-secret",
                "name": "Secret Bot",
                "bot_token": "123:tok",
                "webhook_secret": "my-secret",
            },
        )
        assert resp.status_code == 201
        assert resp.json()["webhook_secret"] == "my-secret"

    def test_create_with_channel_bindings(self, client: TestClient) -> None:
        resp = client.post(
            "/api/v1/telegram-bots",
            json={
                "bot_id": "bot-bind",
                "name": "Bound Bot",
                "bot_token": "123:tok",
                "channel_bindings": ["chan-1", "chan-2"],
            },
        )
        assert resp.status_code == 201
        assert resp.json()["channel_bindings"] == ["chan-1", "chan-2"]
