"""Test fixtures for knowledge-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.knowledge_api.routes import knowledge_store_provider, router
from lintel.knowledge_api.store import InMemoryKnowledgeStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryKnowledgeStore()
    knowledge_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    knowledge_store_provider.override(None)
