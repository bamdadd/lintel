"""Test fixtures for web-ide-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.web_ide_api.routes import ide_session_store_provider, router
from lintel.web_ide_api.store import InMemoryIDESessionStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryIDESessionStore()
    ide_session_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    ide_session_store_provider.override(None)
