"""Test fixtures for artifacts-api package."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.artifacts_api.routes import (
    artifact_content_store_provider,
    code_artifact_store_provider,
    coverage_metric_store_provider,
    parsed_result_store_provider,
    pipeline_store_provider,
    quality_gate_rule_store_provider,
    router,
    test_result_store_provider,
)
from lintel.artifacts_api.store import (
    CodeArtifactStore,
    CoverageMetricStore,
    ParsedTestResultStore,
    QualityGateRuleStore,
    TestResultStore,
)

if TYPE_CHECKING:
    from collections.abc import Generator


class _FakeArtifactContentStore:
    """Minimal ArtifactStore stub for tests."""

    def __init__(self) -> None:
        self._content: dict[str, bytes] = {}

    async def store(self, artifact_id: str, content: bytes, metadata: dict[str, object]) -> str:
        self._content[artifact_id] = content
        return f"mem://{artifact_id}"

    async def retrieve(self, artifact_id: str) -> bytes:
        if artifact_id not in self._content:
            raise KeyError(artifact_id)
        return self._content[artifact_id]

    async def list_refs(self, run_id: str) -> list[object]:
        return []


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
    artifact_content_store_provider.override(_FakeArtifactContentStore())
    parsed_result_store_provider.override(ParsedTestResultStore())
    coverage_metric_store_provider.override(CoverageMetricStore())
    quality_gate_rule_store_provider.override(QualityGateRuleStore())
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    code_artifact_store_provider.override(None)
    test_result_store_provider.override(None)
    pipeline_store_provider.override(None)
    artifact_content_store_provider.override(None)
    parsed_result_store_provider.override(None)
    coverage_metric_store_provider.override(None)
    quality_gate_rule_store_provider.override(None)
