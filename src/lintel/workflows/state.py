"""Workflow state definitions. TypedDict for LangGraph compatibility."""

from __future__ import annotations

from operator import add
from typing import Annotated, Any, TypedDict


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

    # Pipeline tracking
    run_id: str

    # Project & repo context (set by setup_workspace)
    project_id: str
    work_item_id: str
    repo_url: str
    repo_urls: tuple[str, ...]
    repo_branch: str
    feature_branch: str
    credential_ids: tuple[str, ...]
    environment_id: str

    # Workspace path inside sandbox (set by setup_workspace, e.g. /workspace/{run_id}/repo)
    workspace_path: str

    # Research context (populated by the research node for plan/implement)
    research_context: str

    # Token usage tracking (accumulated per node)
    token_usage: Annotated[list[dict[str, Any]], add]
