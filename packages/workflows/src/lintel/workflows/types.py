"""Workflow and pipeline domain types.

Defines types related to workflows, pipelines, stages, and
workflow definitions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from datetime import datetime


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
    QUEUED = "queued"
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
    TIMED_OUT = "timed_out"


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
    trigger_context: str = ""
    environment_id: str = ""
    created_at: str = ""


class RecoveryStrategy(StrEnum):
    """How to recover when a workflow step fails."""

    RETRY = "retry"  # Re-run the same step from scratch
    SKIP = "skip"  # Mark stage as skipped and continue the pipeline
    FAIL_FAST = "fail_fast"  # Immediately fail the pipeline (default behaviour)


class ErrorCategory(StrEnum):
    """Classification of workflow step errors for recovery decisions."""

    TRANSIENT = "transient"  # Network/timeout/rate-limit — safe to retry
    DETERMINISTIC = "deterministic"  # Bad input/validation — retry won't help
    RESOURCE = "resource"  # OOM/disk/sandbox — may recover after backoff
    UNKNOWN = "unknown"  # Unclassified errors


@dataclass(frozen=True)
class RetryPolicy:
    """Configurable retry behaviour for a workflow step.

    Attributes:
        max_retries: Maximum number of automatic retry attempts (0 = no auto-retry).
        backoff_seconds: Initial delay before the first retry.
        backoff_multiplier: Multiplier applied to backoff_seconds after each attempt.
        max_backoff_seconds: Upper bound on backoff delay.
        retryable_categories: Error categories eligible for auto-retry.
        recovery_strategy: What to do when all retries are exhausted.
    """

    max_retries: int = 2
    backoff_seconds: float = 5.0
    backoff_multiplier: float = 2.0
    max_backoff_seconds: float = 120.0
    retryable_categories: tuple[ErrorCategory, ...] = (
        ErrorCategory.TRANSIENT,
        ErrorCategory.RESOURCE,
    )
    recovery_strategy: RecoveryStrategy = RecoveryStrategy.FAIL_FAST


@dataclass(frozen=True)
class StepTimeoutConfig:
    """Per-pipeline timeout configuration for step execution.

    Attributes:
        default_seconds: Default timeout per step (default: 2 hours).
        aggregate_seconds: Optional pipeline-level total timeout across all steps.
    """

    default_seconds: int = 7200
    aggregate_seconds: int | None = None


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
    timeout_seconds: int | None = None
    retry_policy: RetryPolicy | None = None


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


# --- Human Interrupt Types (shared by F013, F017, F018) ---


class InterruptType(StrEnum):
    """Type of human interrupt in a workflow."""

    APPROVAL_GATE = "approval_gate"
    EDITABLE_REPORT = "editable_report"
    HUMAN_TASK = "human_task"


class InterruptStatus(StrEnum):
    """Lifecycle status of a human interrupt."""

    PENDING = "pending"
    RESUMED = "resumed"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class InterruptRequest:
    """Payload emitted when a workflow node requests human input.

    Passed to ``langgraph.types.interrupt()`` and persisted in the
    ``human_interrupts`` table so the resume API can correlate.
    """

    id: UUID = field(default_factory=uuid4)
    run_id: str = ""
    stage: str = ""
    interrupt_type: InterruptType = InterruptType.APPROVAL_GATE
    payload: dict[str, Any] = field(default_factory=dict)
    timeout_seconds: int = 0
    deadline: datetime | None = None


@dataclass(frozen=True)
class InterruptResumeInput:
    """Human-supplied input that resumes a paused interrupt."""

    input: Any = None
    resumed_by: str = ""


@dataclass(frozen=True)
class TimeoutSentinel:
    """Marker value passed as resume input when an interrupt times out.

    Subclasses inspect ``isinstance(human_input, TimeoutSentinel)`` to decide
    whether to auto-proceed or auto-escalate.
    """

    reason: str = "deadline_exceeded"


@dataclass(frozen=True)
class InterruptRecord:
    """Persisted state of a human interrupt."""

    id: UUID = field(default_factory=uuid4)
    run_id: str = ""
    stage: str = ""
    interrupt_type: InterruptType = InterruptType.APPROVAL_GATE
    payload: dict[str, Any] = field(default_factory=dict)
    status: InterruptStatus = InterruptStatus.PENDING
    deadline: datetime | None = None
    resumed_by: str | None = None
    resume_input: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(frozen=True)
class ApprovalGateConfig:
    """Configuration for a confidence-based approval gate.

    When the workflow's confidence score exceeds ``confidence_threshold``,
    the gate auto-approves without human intervention.  Otherwise it
    interrupts and waits for a human decision.
    """

    confidence_threshold: float = 0.8
    timeout_seconds: int = 3600
    required_approvers: int = 1
    notification_channels: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovalDecision:
    """Human decision captured when an approval gate is resumed."""

    approved: bool = False
    approver: str = ""
    corrections: str = ""
    feedback: str = ""


@dataclass(frozen=True)
class VerificationResult:
    """Result of comparing plan tasks against actual file modifications in the sandbox."""

    completeness_score: float
    addressed_tasks: tuple[str, ...]
    unaddressed_tasks: tuple[str, ...]
    modified_files: tuple[str, ...]
    attempt_count: int
