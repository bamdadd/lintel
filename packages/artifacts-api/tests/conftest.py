"""Test fixtures for artifacts-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.artifacts_api.routes import (
    code_artifact_store_provider,
    pipeline_store_provider,
    router,
    test_result_store_provider,
)
from lintel.artifacts_api.store import CodeArtifactStore, TestResultStore

if TYPE_CHECKING:
    from collections.abc import Generator


class _FakePipelineStore:
    """Minimal pipeline store stub for artifact stream tests."""

    def __init__(self) -> None:
        self._runs: dict[str, object] = {}

    async def get(self, run_id: str) -> object | None:
        return self._runs.get(run_id)


@pytest.fixture()
def fake_pipeline_store() -> _FakePipelineStore:
    return _FakePipelineStore()


@pytest.fixture()
def client(fake_pipeline_store: _FakePipelineStore) -> Generator[TestClient]:
    code_artifact_store_provider.override(CodeArtifactStore())
    test_result_store_provider.override(TestResultStore())
    pipeline_store_provider.override(fake_pipeline_store)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    code_artifact_store_provider.override(None)
    test_result_store_provider.override(None)
    pipeline_store_provider.override(None)
