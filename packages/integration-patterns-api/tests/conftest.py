"""Test fixtures for integration-patterns-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.integration_patterns_api import router
from lintel.integration_patterns_api.routes import integration_pattern_store_provider
from lintel.integration_patterns_api.store import InMemoryIntegrationPatternStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def store() -> InMemoryIntegrationPatternStore:
    return InMemoryIntegrationPatternStore()


@pytest.fixture()
def client(store: InMemoryIntegrationPatternStore) -> Generator[TestClient]:
    integration_pattern_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    integration_pattern_store_provider.override(None)
