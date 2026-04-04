"""Test fixtures for bots-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.bots_api.routes import bot_store_provider, router
from lintel.bots_api.store import InMemoryBotStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryBotStore()
    bot_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    bot_store_provider.override(None)
