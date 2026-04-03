"""Test fixtures for tech-spec-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.tech_spec_api.routes import router, tech_spec_store_provider
from lintel.tech_spec_api.store import InMemoryTechSpecStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryTechSpecStore()
    tech_spec_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    tech_spec_store_provider.override(None)
