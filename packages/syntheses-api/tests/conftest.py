"""Test fixtures for syntheses-api."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from lintel.syntheses_api.routes import router, synthesis_store_provider
from lintel.syntheses_api.store import SynthesisStore


@pytest.fixture()
def client() -> Generator[TestClient, Any, None]:
    synthesis_store_provider.override(SynthesisStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    synthesis_store_provider.override(None)  # type: ignore[arg-type]
