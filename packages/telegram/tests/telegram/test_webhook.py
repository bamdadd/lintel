"""Tests for Telegram webhook endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from lintel.multi_telegram_bot_api.routes import telegram_bot_store_provider
from lintel.multi_telegram_bot_api.store import InMemoryTelegramBotStore, TelegramBot
from lintel.telegram.webhook import router


def _create_app(adapter: object | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    if adapter is not None:
        app.state.telegram_adapter = adapter
    return app


def _create_bot_app(store: InMemoryTelegramBotStore) -> FastAPI:
    """Create an app with the per-bot webhook and a telegram bot store."""
    telegram_bot_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return app


class TestWebhookEndpoint:
    def test_returns_503_when_not_configured(self) -> None:
        app = _create_app(adapter=None)
        client = TestClient(app)
        resp = client.post("/api/v1/channels/telegram/webhook", json={})
        assert resp.status_code == 503

    def test_returns_403_for_invalid_secret(self) -> None:
        adapter = AsyncMock()
        adapter.webhook_secret = "correct-secret"
        app = _create_app(adapter=adapter)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/channels/telegram/webhook",
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
        )
        assert resp.status_code == 403

    def test_accepts_valid_secret(self) -> None:
        adapter = AsyncMock()
        adapter.webhook_secret = "correct-secret"
        adapter.bot_username = "testbot"
        app = _create_app(adapter=adapter)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/channels/telegram/webhook",
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "correct-secret"},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

    def test_handles_message_update(self) -> None:
        adapter = AsyncMock()
        adapter.webhook_secret = ""
        adapter.bot_username = ""
        app = _create_app(adapter=adapter)
        client = TestClient(app)
        update = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 123},
                "chat": {"id": 456, "type": "private"},
                "text": "Hello",
            },
        }
        resp = client.post("/api/v1/channels/telegram/webhook", json=update)
        assert resp.status_code == 200

    def test_handles_callback_query(self) -> None:
        adapter = AsyncMock()
        adapter.webhook_secret = ""
        adapter.bot_username = ""
        adapter.answer_callback_query = AsyncMock(return_value={})
        app = _create_app(adapter=adapter)
        client = TestClient(app)
        update = {
            "update_id": 2,
            "callback_query": {
                "id": "cb-1",
                "from": {"id": 123},
                "data": "a:req-456",
            },
        }
        resp = client.post("/api/v1/channels/telegram/webhook", json=update)
        assert resp.status_code == 200


class TestPerBotWebhook:
    """Tests for the per-bot webhook at /channels/telegram/webhook/{bot_id}."""

    def test_returns_404_for_unknown_bot(self) -> None:
        store = InMemoryTelegramBotStore()
        app = _create_bot_app(store)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/channels/telegram/webhook/unknown-bot",
            json={"update_id": 1},
        )
        assert resp.status_code == 404
        telegram_bot_store_provider.override(None)

    def test_returns_403_for_disabled_bot(self) -> None:
        store = InMemoryTelegramBotStore()
        bot = TelegramBot(bot_id="disabled-bot", bot_token="tok", enabled=False)
        store._bots[bot.bot_id] = bot
        app = _create_bot_app(store)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/channels/telegram/webhook/disabled-bot",
            json={"update_id": 1},
        )
        assert resp.status_code == 403
        telegram_bot_store_provider.override(None)

    def test_returns_403_for_invalid_secret(self) -> None:
        store = InMemoryTelegramBotStore()
        bot = TelegramBot(bot_id="secret-bot", bot_token="tok", webhook_secret="correct")
        store._bots[bot.bot_id] = bot
        app = _create_bot_app(store)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/channels/telegram/webhook/secret-bot",
            json={"update_id": 1},
            headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
        )
        assert resp.status_code == 403
        telegram_bot_store_provider.override(None)

    def test_accepts_valid_bot_no_secret(self) -> None:
        store = InMemoryTelegramBotStore()
        bot = TelegramBot(bot_id="good-bot", bot_token="tok")
        store._bots[bot.bot_id] = bot
        app = _create_bot_app(store)
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post(
            "/api/v1/channels/telegram/webhook/good-bot",
            json={"update_id": 1},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        telegram_bot_store_provider.override(None)

    def test_handles_message_update_for_bot(self) -> None:
        store = InMemoryTelegramBotStore()
        bot = TelegramBot(bot_id="msg-bot", bot_token="tok")
        store._bots[bot.bot_id] = bot
        app = _create_bot_app(store)
        client = TestClient(app, raise_server_exceptions=False)
        update = {
            "update_id": 1,
            "message": {
                "message_id": 42,
                "from": {"id": 123},
                "chat": {"id": 456, "type": "private"},
                "text": "Hello from bot",
            },
        }
        resp = client.post(
            "/api/v1/channels/telegram/webhook/msg-bot",
            json=update,
        )
        assert resp.status_code == 200
        telegram_bot_store_provider.override(None)

    def test_handles_callback_query_for_bot(self) -> None:
        store = InMemoryTelegramBotStore()
        bot = TelegramBot(bot_id="cb-bot", bot_token="tok")
        store._bots[bot.bot_id] = bot
        app = _create_bot_app(store)
        client = TestClient(app, raise_server_exceptions=False)
        update = {
            "update_id": 2,
            "callback_query": {
                "id": "cb-1",
                "from": {"id": 123},
                "data": "a:req-789",
            },
        }
        resp = client.post(
            "/api/v1/channels/telegram/webhook/cb-bot",
            json=update,
        )
        assert resp.status_code == 200
        telegram_bot_store_provider.override(None)
