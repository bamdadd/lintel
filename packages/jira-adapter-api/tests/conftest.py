"""Test fixtures for jira-adapter-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.jira_adapter_api.routes import (
    jira_connection_store_provider,
    router,
    sync_record_store_provider,
    work_item_store_provider,
)
from lintel.jira_adapter_api.store import InMemoryJiraConnectionStore, InMemorySyncRecordStore

if TYPE_CHECKING:
    from collections.abc import Generator


class _FakeWorkItemStore:
    pass


@pytest.fixture()
def client() -> Generator[TestClient]:
    conn_store = InMemoryJiraConnectionStore()
    sync_store = InMemorySyncRecordStore()
    jira_connection_store_provider.override(conn_store)
    sync_record_store_provider.override(sync_store)
    work_item_store_provider.override(_FakeWorkItemStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    jira_connection_store_provider.override(None)
    sync_record_store_provider.override(None)
    work_item_store_provider.override(None)
