"""Test fixtures for agent-metrics-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.agent_metrics_api.routes import agent_metrics_store_provider, router
from lintel.agent_metrics_api.store import InMemoryAgentMetricsStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryAgentMetricsStore()
    agent_metrics_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    agent_metrics_store_provider.override(None)
