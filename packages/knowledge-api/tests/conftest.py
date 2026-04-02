"""Test fixtures for knowledge-api."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from lintel.knowledge_api.routes import knowledge_edge_store_provider, router
from lintel.knowledge_api.store import KnowledgeEdgeStore


@pytest.fixture()
def client() -> Generator[TestClient, Any, None]:
    knowledge_edge_store_provider.override(KnowledgeEdgeStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    knowledge_edge_store_provider.override(None)  # type: ignore[arg-type]
