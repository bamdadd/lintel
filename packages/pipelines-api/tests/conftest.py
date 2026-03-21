"""Test configuration for lintel-pipelines-api."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from lintel.pipelines_api._store import InMemoryPipelineStore, pipeline_store_provider
from lintel.pipelines_api.stages import router as stages_router
from lintel.workflows.types import PipelineRun, PipelineStatus, Stage, StageStatus

if TYPE_CHECKING:
    from collections.abc import Generator


@pytest.fixture()
def store() -> InMemoryPipelineStore:
    return InMemoryPipelineStore()


@pytest.fixture()
def client(store: InMemoryPipelineStore) -> Generator[TestClient]:
    pipeline_store_provider.override(store)
    app = FastAPI()
    app.include_router(stages_router, prefix="/api/v1")
    with TestClient(app) as c:
        yield c
    pipeline_store_provider.override(None)


@pytest.fixture()
def sample_run() -> PipelineRun:
    """A pipeline run with a research stage in waiting_approval status."""
    return PipelineRun(
        run_id="run-1",
        project_id="proj-1",
        work_item_id="wi-1",
        workflow_definition_id="feature_to_pr",
        status=PipelineStatus.WAITING_APPROVAL,
        stages=(
            Stage(
                stage_id="stage-research",
                name="research",
                stage_type="research",
                status=StageStatus.WAITING_APPROVAL,
                outputs={"research_report": "# Original Report\n\nSome content."},
            ),
            Stage(
                stage_id="stage-plan",
                name="plan",
                stage_type="plan",
                status=StageStatus.PENDING,
            ),
        ),
    )
