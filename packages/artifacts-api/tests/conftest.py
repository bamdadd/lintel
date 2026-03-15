"""Test fixtures for artifacts-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.artifacts_api.routes import (
    router,
    code_artifact_store_provider,
    test_result_store_provider,
)
from lintel.artifacts_api.store import CodeArtifactStore, TestResultStore

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def client() -> Generator[TestClient]:
    code_artifact_store_provider.override(CodeArtifactStore())
    test_result_store_provider.override(TestResultStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    code_artifact_store_provider.override(None)
    test_result_store_provider.override(None)
