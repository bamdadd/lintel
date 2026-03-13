"""Pipeline response models."""

from typing import Any

from pydantic import BaseModel


class StageResponse(BaseModel):
    stage_id: str
    name: str
    stage_type: str = ""
    status: str = "pending"
    inputs: dict[str, Any] | None = None
    outputs: dict[str, Any] | None = None
    error: str | None = None
    duration_ms: int | None = None


class PipelineRunResponse(BaseModel):
    run_id: str
    project_id: str
    work_item_id: str
    workflow_definition_id: str = "feature_to_pr"
    status: str = "pending"
    stages: list[StageResponse] = []
    trigger_type: str = ""
    trigger_id: str = ""
