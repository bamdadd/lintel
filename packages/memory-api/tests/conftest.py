"""Test fixtures for memory-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.memory_api.dependencies import memory_service_provider
from lintel.memory_api.routes import router

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def mock_memory_service():
    service = AsyncMock()
    return service


@pytest.fixture()
def client(mock_memory_service) -> Generator[TestClient]:
    memory_service_provider.override(mock_memory_service)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    memory_service_provider.override(None)
