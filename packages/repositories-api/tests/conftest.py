"""Test fixtures for repositories-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.repos.repository_store import InMemoryRepositoryStore
from lintel.repositories_api.routes import (
    repo_provider_provider,
    repository_store_provider,
    router,
)

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryRepositoryStore()
    repository_store_provider.override(store)
    repo_provider_provider.override(None)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    repository_store_provider.override(None)
    repo_provider_provider.override(None)
