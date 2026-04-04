"""Test fixtures for multi-telegram-bot-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.multi_telegram_bot_api.routes import router, telegram_bot_store_provider
from lintel.multi_telegram_bot_api.store import InMemoryTelegramBotStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryTelegramBotStore()
    telegram_bot_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    telegram_bot_store_provider.override(None)
