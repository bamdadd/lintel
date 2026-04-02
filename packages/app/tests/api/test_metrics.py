"""Tests for the metrics API endpoints."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from fastapi.testclient import TestClient

from lintel.api.app import create_app


@pytest.fixture()
def client() -> Generator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


class TestMetricsAPI:
    def test_pii_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/pii")
        assert resp.status_code == 200
        data = resp.json()
        assert "pii" in data
        assert "total_scanned" in data["pii"]

    def test_agent_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/agents")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_steps" in data
        assert "activity" in data

    def test_overview_metrics(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/overview")
        assert resp.status_code == 200
        data = resp.json()
        assert "pii" in data
        assert "sandboxes" in data
        assert "connections" in data

    def test_quality_metrics_default(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/quality")
        assert resp.status_code == 200
        data = resp.json()
        assert "coverage_deltas" in data
        assert "defect_density" in data
        assert "rework_ratio" in data
        assert data["window_days"] == 30
        assert data["defect_density"]["density"] == 0.0
        assert data["rework_ratio"]["ratio"] == 0.0

    def test_quality_metrics_with_window(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/quality?days=90")
        assert resp.status_code == 200
        data = resp.json()
        assert data["window_days"] == 90

    def test_quality_metrics_with_project_filter(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/quality?project_id=proj-1&days=60")
        assert resp.status_code == 200
        data = resp.json()
        assert data["defect_density"]["window_days"] == 60

    def test_pipeline_metrics_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/metrics/pipelines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 0
        assert data["success_rate"] == 0.0
        assert data["runs_over_time"] == []
        assert data["failure_reasons"] == []

    def test_pipeline_metrics_with_runs(self, client: TestClient) -> None:
        from lintel.pipelines_api._store import InMemoryPipelineStore
        from lintel.workflows.types import (
            PipelineRun,
            PipelineStatus,
            Stage,
            StageStatus,
        )

        store = InMemoryPipelineStore()
        client.app.state.pipeline_store = store  # type: ignore[union-attr]

        import asyncio

        loop = asyncio.new_event_loop()
        loop.run_until_complete(
            store.add(
                PipelineRun(
                    run_id="r1",
                    project_id="p1",
                    work_item_id="w1",
                    workflow_definition_id="feature_to_pr",
                    status=PipelineStatus.SUCCEEDED,
                    stages=(
                        Stage(
                            stage_id="s1",
                            name="research",
                            stage_type="research",
                            status=StageStatus.SUCCEEDED,
                            duration_ms=5000,
                        ),
                    ),
                    created_at="2026-04-01T10:00:00+00:00",
                )
            )
        )
        loop.run_until_complete(
            store.add(
                PipelineRun(
                    run_id="r2",
                    project_id="p1",
                    work_item_id="w2",
                    workflow_definition_id="feature_to_pr",
                    status=PipelineStatus.FAILED,
                    stages=(
                        Stage(
                            stage_id="s2",
                            name="implement",
                            stage_type="implement",
                            status=StageStatus.FAILED,
                            error="Compilation error",
                        ),
                    ),
                    created_at="2026-04-01T12:00:00+00:00",
                )
            )
        )
        loop.close()

        resp = client.get("/api/v1/metrics/pipelines")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_runs"] == 2
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        assert data["success_rate"] == 50.0
        assert data["avg_duration_ms"] == 5000
        assert len(data["runs_over_time"]) == 1
        assert data["runs_over_time"][0]["date"] == "2026-04-01"
        assert len(data["failure_reasons"]) == 1
        assert data["failure_reasons"][0]["reason"] == "Compilation error"
