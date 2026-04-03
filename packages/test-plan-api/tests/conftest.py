"""Test fixtures for test-plan-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.test_plan_api.routes import router, test_plan_store_provider
from lintel.test_plan_api.store import InMemoryTestPlanStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryTestPlanStore()
    test_plan_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    test_plan_store_provider.override(None)
