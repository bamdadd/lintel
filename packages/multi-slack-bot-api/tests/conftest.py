"""Test fixtures for multi-slack-bot-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.multi_slack_bot_api.routes import router, slack_bot_store_provider
from lintel.multi_slack_bot_api.store import InMemorySlackBotStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemorySlackBotStore()
    slack_bot_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    slack_bot_store_provider.override(None)
