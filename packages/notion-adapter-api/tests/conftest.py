"""Test fixtures for notion-adapter-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.notion_adapter_api.routes import (
    notion_connection_store_provider,
    router,
    webhook_secret_provider,
)
from lintel.notion_adapter_api.store import InMemoryNotionConnectionStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryNotionConnectionStore()
    notion_connection_store_provider.override(store)
    app = FastAPI()
    # Provide a mock event bus so dispatch_event doesn't fail
    app.state.event_bus = AsyncMock()
    app.include_router(router, prefix="/api/v1")
    # Ensure no webhook secret is configured by default (skip sig verification)
    webhook_secret_provider.override(None)
    with TestClient(app) as c:
        yield c
    notion_connection_store_provider.override(None)
    webhook_secret_provider.override(None)
