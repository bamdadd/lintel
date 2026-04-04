"""Test fixtures for board-sync-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.board_sync_api.routes import (
    mapping_store_provider,
    router,
    sync_config_store_provider,
)
from lintel.board_sync_api.store import BoardSyncConfigStore, ExternalIdMappingStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    sync_config_store_provider.override(BoardSyncConfigStore())
    mapping_store_provider.override(ExternalIdMappingStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    sync_config_store_provider.override(None)
    mapping_store_provider.override(None)
