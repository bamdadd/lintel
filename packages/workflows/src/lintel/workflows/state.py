"""Workflow state definitions. TypedDict for LangGraph compatibility."""

from __future__ import annotations

from operator import add
from typing import TYPE_CHECKING, Annotated, Any, TypedDict

if TYPE_CHECKING:
    from lintel.workflows.types import VerificationResult


class ThreadWorkflowState(TypedDict):
    """State for the feature-to-PR workflow graph."""

    thread_ref: str
    correlation_id: str
    current_phase: str
    sanitized_messages: Annotated[list[str], add]
    intent: str
    plan: dict[str, Any]
    agent_outputs: Annotated[list[dict[str, Any]], add]
    pending_approvals: list[str]
    sandbox_id: str | None
    sandbox_results: Annotated[list[dict[str, Any]], add]
    pr_url: str
    error: str | None

    # Trigger context (JSON string from the triggering endpoint, e.g. regulation IDs)
    trigger_context: str

    # Pipeline tracking
    run_id: str

    # Project & repo context (set by setup_workspace)
    project_id: str
    work_item_id: str
    work_item_title: str
    repo_url: str
    repo_urls: tuple[str, ...]
    repo_branch: str
    feature_branch: str
    credential_ids: tuple[str, ...]
    environment_id: str

    # Workspace path inside sandbox (set by setup_workspace, e.g. /workspace/{run_id}/repo)
    workspace_path: str

    # All workspace paths for multi-repo projects (repo_url → workspace dir)
    # First entry is always the primary repo. Empty tuple for single-repo projects.
    workspace_paths: tuple[tuple[str, str], ...]

    # Research context (populated by the research node for plan/implement)
    research_context: str

    # Token usage tracking (accumulated per node)
    token_usage: Annotated[list[dict[str, Any]], add]

    # Review cycle counter (implement ↔ review loop)
    review_cycles: int

    # Per-project configurable max review cycles (set from Project.max_review_cycles)
    max_review_cycles: int

    # Set to True when the review circuit breaker force-approved
    review_circuit_breaker_tripped: bool

    # Pipeline continuation — populated when rehydrating from a previous failed run
    previous_error: str
    previous_failed_stage: str

    # Project conventions — concatenated CLAUDE.md file contents from the target repo.
    # Collected by setup_workspace and injected into implement/review agent system prompts.
    project_conventions: str

    # Implementation verification (verify_implementation node)
    # Result of comparing plan tasks against actual sandbox file modifications.
    verification_result: VerificationResult | None
    # Human-readable summary of unaddressed tasks, fed back to the coder on retry.
    verification_feedback: str | None
    # Loop guard: number of implement attempts (incremented each loop-back).
    implement_attempt_count: int
