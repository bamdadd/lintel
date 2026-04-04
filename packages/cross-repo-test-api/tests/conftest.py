"""Test fixtures for cross-repo-test-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.cross_repo_test_api.routes import router, test_run_store_provider
from lintel.cross_repo_test_api.store import InMemoryTestRunStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryTestRunStore()
    test_run_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    test_run_store_provider.override(None)
