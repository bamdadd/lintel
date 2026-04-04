"""Test fixtures for multiplayer-sessions-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.multiplayer_sessions_api.routes import router, session_store_provider
from lintel.multiplayer_sessions_api.store import InMemorySessionStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    session_store_provider.override(InMemorySessionStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    session_store_provider.override(None)
