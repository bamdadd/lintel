"""Test fixtures for browser-extension-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.browser_extension_api.routes import modification_store_provider, router
from lintel.browser_extension_api.store import InMemoryComponentModificationStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryComponentModificationStore()
    modification_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    modification_store_provider.override(None)
