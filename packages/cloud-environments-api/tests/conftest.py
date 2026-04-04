"""Test fixtures for cloud-environments-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.cloud_environments_api.routes import cloud_environment_store_provider, router
from lintel.cloud_environments_api.store import InMemoryCloudEnvironmentStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryCloudEnvironmentStore()
    cloud_environment_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    cloud_environment_store_provider.override(None)
