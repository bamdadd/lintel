"""Test fixtures for visual-verification-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.visual_verification_api.routes import router, verification_store_provider
from lintel.visual_verification_api.store import InMemoryVisualVerificationStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    store = InMemoryVisualVerificationStore()
    verification_store_provider.override(store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    verification_store_provider.override(None)
