"""Test fixtures for digest-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.digest_api.routes import (
    digest_config_store_provider,
    digest_store_provider,
    router,
)
from lintel.digest_api.store import InMemoryDigestConfigStore, InMemoryDigestStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    digest_store = InMemoryDigestStore()
    config_store = InMemoryDigestConfigStore()
    digest_store_provider.override(digest_store)
    digest_config_store_provider.override(config_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    digest_store_provider.override(None)
    digest_config_store_provider.override(None)
