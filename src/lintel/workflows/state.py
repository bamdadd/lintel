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
