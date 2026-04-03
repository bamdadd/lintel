"""Test fixtures for scheduled-tasks-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.scheduled_tasks_api.routes import router, scheduled_task_store_provider
from lintel.scheduled_tasks_api.store import InMemoryScheduledTaskStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryScheduledTaskStore()
    scheduled_task_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    scheduled_task_store_provider.override(None)
