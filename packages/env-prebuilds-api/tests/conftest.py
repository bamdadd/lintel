"""Test fixtures for env-prebuilds-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.env_prebuilds_api.routes import (
    prebuild_config_store_provider,
    prebuild_run_store_provider,
    router,
)
from lintel.env_prebuilds_api.store import InMemoryPrebuildConfigStore, InMemoryPrebuildRunStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    config_store = InMemoryPrebuildConfigStore()
    run_store = InMemoryPrebuildRunStore()
    prebuild_config_store_provider.override(config_store)
    prebuild_run_store_provider.override(run_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    prebuild_config_store_provider.override(None)
    prebuild_run_store_provider.override(None)
