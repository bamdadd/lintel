"""Test fixtures for work-items-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.work_items_api.routes import router, work_item_store_provider
from lintel.work_items_api.store import WorkItemStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    work_item_store_provider.override(WorkItemStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    work_item_store_provider.override(None)
