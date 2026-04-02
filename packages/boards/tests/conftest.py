"""Test fixtures for boards package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.boards.routes import (
    board_store_provider,
    router,
    tag_store_provider,
    work_item_store_provider,
)
from lintel.boards.store import BoardStore, TagStore
from lintel.work_items_api.store import WorkItemStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    tag_store = TagStore()
    board_store = BoardStore()
    wi_store = WorkItemStore()
    tag_store_provider.override(tag_store)
    board_store_provider.override(board_store)
    work_item_store_provider.override(wi_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    tag_store_provider.override(None)
    board_store_provider.override(None)
    work_item_store_provider.override(None)
