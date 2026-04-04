"""Test fixtures for pipeline-diagnostics-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.pipeline_diagnostics_api.routes import diagnostic_store_provider, router
from lintel.pipeline_diagnostics_api.store import InMemoryPipelineDiagnosticStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    diagnostic_store_provider.override(InMemoryPipelineDiagnosticStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    diagnostic_store_provider.override(None)
