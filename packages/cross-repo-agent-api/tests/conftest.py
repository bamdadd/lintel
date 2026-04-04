"""Test fixtures for cross-repo-agent-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.cross_repo_agent_api.routes import cross_repo_plan_store_provider, router
from lintel.cross_repo_agent_api.store import InMemoryCrossRepoPlanStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryCrossRepoPlanStore()
    cross_repo_plan_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    cross_repo_plan_store_provider.override(None)
