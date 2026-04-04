"""Test fixtures for data-retention-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.data_retention_api.routes import retention_policy_store_provider, router
from lintel.data_retention_api.store import InMemoryRetentionPolicyStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryRetentionPolicyStore()
    retention_policy_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    retention_policy_store_provider.override(None)
