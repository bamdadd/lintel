"""Test fixtures for fleet-execution-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.fleet_execution_api.routes import fleet_run_store_provider, router
from lintel.fleet_execution_api.store import InMemoryFleetRunStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryFleetRunStore()
    fleet_run_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    fleet_run_store_provider.override(None)
