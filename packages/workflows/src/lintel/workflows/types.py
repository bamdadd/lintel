"""Workflow and pipeline domain types.

Defines types related to workflows, pipelines, stages, and
workflow definitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class WorkflowPhase(StrEnum):
    INGESTING = "ingesting"
    PLANNING = "planning"
    AWAITING_SPEC_APPROVAL = "awaiting_spec_approval"
    IMPLEMENTING = "implementing"
    REVIEWING = "reviewing"
    AWAITING_PR_APPROVAL = "awaiting_pr_approval"
    RAISING_PR = "raising_pr"
    CLOSED = "closed"


class PipelineStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StageStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    SKIPPED = "skipped"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass(frozen=True)
class StageAttempt:
    """A single execution attempt of a pipeline stage."""

    attempt: int  # 1-based attempt number
    status: StageStatus = StageStatus.PENDING
    inputs: dict[str, object] | None = None
    outputs: dict[str, object] | None = None
    error: str = ""
    duration_ms: int = 0
    started_at: str = ""
    finished_at: str = ""
    logs: tuple[str, ...] = ()


@dataclass(frozen=True)
class Stage:
    """A single step in a pipeline execution."""

    stage_id: str
    name: str
    stage_type: str  # ingest, plan, approve, implement, test, review, merge
    status: StageStatus = StageStatus.PENDING
    inputs: dict[str, object] | None = None
    outputs: dict[str, object] | None = None
    error: str = ""
    duration_ms: int = 0
    started_at: str = ""
    finished_at: str = ""
    logs: tuple[str, ...] = ()
    retry_count: int = 0
    attempts: tuple[StageAttempt, ...] = ()


@dataclass(frozen=True)
class PipelineRun:
    """A specific execution of a workflow/pipeline."""

    run_id: str
    project_id: str
    work_item_id: str
    workflow_definition_id: str
    status: PipelineStatus = PipelineStatus.PENDING
    stages: tuple[Stage, ...] = ()
    trigger_type: str = ""
    trigger_id: str = ""
    environment_id: str = ""
    created_at: str = ""


@dataclass(frozen=True)
class WorkflowStepConfig:
    """Per-step configuration binding an agent, model, and provider to a workflow node."""

    node_name: str
    agent_id: str = ""
    model_id: str = ""
    provider_id: str = ""
    requires_approval: bool = False
    label: str = ""
    description: str = ""


@dataclass(frozen=True)
class WorkflowDefinitionRecord:
    """A persisted workflow definition template."""

    definition_id: str
    name: str
    description: str = ""
    is_template: bool = False
    stage_names: tuple[str, ...] = ()
    graph_nodes: tuple[str, ...] = ()
    graph_edges: tuple[tuple[str, str], ...] = ()
    conditional_edges: tuple[dict[str, object], ...] = ()
    entry_point: str = ""
    interrupt_before: tuple[str, ...] = ()
    step_configs: tuple[WorkflowStepConfig, ...] = ()
    node_metadata: tuple[dict[str, str], ...] = ()
    tags: tuple[str, ...] = ()
    is_builtin: bool = False
    enabled: bool = True
