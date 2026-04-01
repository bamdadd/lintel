"""Tests for stage report editing endpoints."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from lintel.workflows.types import PipelineRun, PipelineStatus, Stage, StageStatus

if TYPE_CHECKING:
    from fastapi.testclient import TestClient

    from lintel.pipelines_api._store import InMemoryPipelineStore


def _seed(store: InMemoryPipelineStore, run: PipelineRun) -> None:
    """Synchronously add a run to the store."""
    asyncio.run(store.add(run))


class TestEditStageReport:
    """PATCH /pipelines/{run_id}/stages/{stage_id}/report"""

    def test_successful_edit_returns_version_info(
        self,
        client: TestClient,
        store: InMemoryPipelineStore,
        sample_run: PipelineRun,
    ) -> None:
        _seed(store, sample_run)
        resp = client.patch(
            "/api/v1/pipelines/run-1/stages/stage-research/report",
            json={"content": "# Updated Report\n\nNew content.", "editor": "alice"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["stage_id"] == "stage-research"
        assert data["report_key"] == "research_report"
        assert data["version"] == 1
        assert data["content"] == "# Updated Report\n\nNew content."

    def test_edit_nonexistent_run_returns_404(
        self,
        client: TestClient,
    ) -> None:
        resp = client.patch(
            "/api/v1/pipelines/no-such-run/stages/stage-research/report",
            json={"content": "x"},
        )
        assert resp.status_code == 404
        assert "Pipeline run not found" in resp.json()["detail"]

    def test_edit_report_wrong_status_returns_409(
        self,
        client: TestClient,
        store: InMemoryPipelineStore,
    ) -> None:
        run = PipelineRun(
            run_id="run-pending",
            project_id="proj-1",
            work_item_id="wi-1",
            workflow_definition_id="feature_to_pr",
            status=PipelineStatus.RUNNING,
            stages=(
                Stage(
                    stage_id="stage-r",
                    name="research",
                    stage_type="research",
                    status=StageStatus.RUNNING,
                ),
            ),
        )
        _seed(store, run)
        resp = client.patch(
            "/api/v1/pipelines/run-pending/stages/stage-r/report",
            json={"content": "x"},
        )
        assert resp.status_code == 409
        assert "Cannot edit report" in resp.json()["detail"]


class TestListReportVersions:
    """GET /pipelines/{run_id}/stages/{stage_id}/report/versions"""

    def test_returns_version_list_after_edit(
        self,
        client: TestClient,
        store: InMemoryPipelineStore,
        sample_run: PipelineRun,
    ) -> None:
        _seed(store, sample_run)
        # Make an edit first to create a version
        client.patch(
            "/api/v1/pipelines/run-1/stages/stage-research/report",
            json={"content": "v1 content", "editor": "bob"},
        )
        resp = client.get(
            "/api/v1/pipelines/run-1/stages/stage-research/report/versions",
        )
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) == 1
        assert versions[0]["version"] == 1
        assert versions[0]["editor"] == "bob"
        assert versions[0]["type"] == "edit"

    def test_returns_empty_list_with_no_edits(
        self,
        client: TestClient,
        store: InMemoryPipelineStore,
        sample_run: PipelineRun,
    ) -> None:
        _seed(store, sample_run)
        resp = client.get(
            "/api/v1/pipelines/run-1/stages/stage-research/report/versions",
        )
        assert resp.status_code == 200
        assert resp.json() == []


class TestRegenerateStage:
    """POST /pipelines/{run_id}/stages/{stage_id}/regenerate"""

    def test_regenerate_sets_stage_to_running(
        self,
        client: TestClient,
        store: InMemoryPipelineStore,
        sample_run: PipelineRun,
    ) -> None:
        _seed(store, sample_run)
        resp = client.post(
            "/api/v1/pipelines/run-1/stages/stage-research/regenerate",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["stage_id"] == "stage-research"
        assert data["retry_count"] == 1

    def test_regenerate_with_guidance_stores_guidance(
        self,
        client: TestClient,
        store: InMemoryPipelineStore,
        sample_run: PipelineRun,
    ) -> None:
        _seed(store, sample_run)
        resp = client.post(
            "/api/v1/pipelines/run-1/stages/stage-research/regenerate",
            json={"guidance": "Focus on security aspects"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["inputs"]["regenerate_guidance"] == "Focus on security aspects"

    def test_regenerate_nonexistent_run_returns_404(
        self,
        client: TestClient,
    ) -> None:
        resp = client.post(
            "/api/v1/pipelines/no-such-run/stages/stage-research/regenerate",
            json={},
        )
        assert resp.status_code == 404
        assert "Pipeline run not found" in resp.json()["detail"]
