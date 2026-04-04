"""Tests for bot health endpoints."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.bot_runtime.types import BotConnectionState, BotHealth
from lintel.bots_api.routes import bot_store_provider, router
from lintel.bots_api.store import InMemoryBotStore


class FakeLifecycleManager:
    """Minimal stub for BotLifecycleManager."""

    def __init__(self) -> None:
        self._health: dict[str, BotHealth] = {}

    def set_health(
        self, bot_id: str, state: BotConnectionState = BotConnectionState.CONNECTED
    ) -> None:
        h = BotHealth(bot_id=bot_id, state=state)
        h.touch()
        self._health[bot_id] = h

    def get_health(self, bot_id: str) -> BotHealth | None:
        return self._health.get(bot_id)

    def get_all_health(self) -> list[BotHealth]:
        return list(self._health.values())

    async def restart_bot(self, bot_id: str) -> bool:
        h = self._health.get(bot_id)
        if h is None:
            return False
        h.mark_connected()
        return True


@pytest.fixture()
def health_client() -> TestClient:
    store = InMemoryBotStore()
    bot_store_provider.override(store)
    app = FastAPI()
    mgr = FakeLifecycleManager()
    mgr.set_health("b1", BotConnectionState.CONNECTED)
    mgr.set_health("b2", BotConnectionState.FAILED)
    app.state.bot_lifecycle_manager = mgr
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    bot_store_provider.override(None)


class TestBotHealth:
    def test_list_health(self, health_client: TestClient) -> None:
        resp = health_client.get("/api/v1/bots/health")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        ids = {h["bot_id"] for h in data}
        assert ids == {"b1", "b2"}

    def test_get_health_connected(self, health_client: TestClient) -> None:
        resp = health_client.get("/api/v1/bots/b1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["bot_id"] == "b1"
        assert data["state"] == "connected"

    def test_get_health_failed(self, health_client: TestClient) -> None:
        resp = health_client.get("/api/v1/bots/b2/health")
        assert resp.status_code == 200
        assert resp.json()["state"] == "failed"

    def test_get_health_not_found(self, health_client: TestClient) -> None:
        resp = health_client.get("/api/v1/bots/missing/health")
        assert resp.status_code == 404

    def test_restart_bot(self, health_client: TestClient) -> None:
        resp = health_client.post("/api/v1/bots/b1/restart")
        assert resp.status_code == 200
        assert resp.json()["state"] == "connected"

    def test_restart_bot_not_found(self, health_client: TestClient) -> None:
        resp = health_client.post("/api/v1/bots/missing/restart")
        assert resp.status_code == 404


class TestHealthWithoutManager:
    def test_health_returns_503_without_manager(self) -> None:
        store = InMemoryBotStore()
        bot_store_provider.override(store)
        app = FastAPI()
        # No bot_lifecycle_manager on app.state
        app.include_router(router, prefix="/api/v1")
        with TestClient(app) as c:
            resp = c.get("/api/v1/bots/health")
            assert resp.status_code == 503
        bot_store_provider.override(None)
