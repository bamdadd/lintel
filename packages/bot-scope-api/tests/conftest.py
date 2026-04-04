"""Test fixtures for bot-scope-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.bot_scope_api.routes import bot_scope_store_provider, router
from lintel.bot_scope_api.store import InMemoryBotScopeStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryBotScopeStore()
    bot_scope_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    bot_scope_store_provider.override(None)
