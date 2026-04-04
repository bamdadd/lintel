"""Test fixtures for proactive-triggers-api."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.proactive_triggers_api.routes import (
    proactive_trigger_store_provider,
    router,
    trigger_execution_store_provider,
)
from lintel.proactive_triggers_api.store import (
    InMemoryProactiveTriggerStore,
    InMemoryTriggerExecutionStore,
)


@pytest.fixture()
def trigger_store() -> InMemoryProactiveTriggerStore:
    return InMemoryProactiveTriggerStore()


@pytest.fixture()
def execution_store() -> InMemoryTriggerExecutionStore:
    return InMemoryTriggerExecutionStore()


@pytest.fixture()
def client(
    trigger_store: InMemoryProactiveTriggerStore,
    execution_store: InMemoryTriggerExecutionStore,
) -> TestClient:
    proactive_trigger_store_provider.override(trigger_store)
    trigger_execution_store_provider.override(execution_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    return TestClient(app)
