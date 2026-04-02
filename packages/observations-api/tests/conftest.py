"""Test fixtures for observations-api."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

if TYPE_CHECKING:
    from collections.abc import Generator

from lintel.observations_api.routes import observation_store_provider, router
from lintel.observations_api.store import ObservationStore


@pytest.fixture()
def client() -> Generator[TestClient, Any, None]:
    observation_store_provider.override(ObservationStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    observation_store_provider.override(None)  # type: ignore[arg-type]
