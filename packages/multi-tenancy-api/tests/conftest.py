"""Test fixtures for multi-tenancy-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.multi_tenancy_api.routes import router, workspace_store_provider
from lintel.multi_tenancy_api.store import InMemoryWorkspaceStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryWorkspaceStore()
    workspace_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    workspace_store_provider.override(None)
