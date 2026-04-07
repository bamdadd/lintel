"""Change-request workflow graph — re-implement loop from Slack feedback.

When a user replies to a completed workflow thread with change requests, this
shorter pipeline re-enters the implement → review → close cycle on the same
feature branch.  It skips research/plan because the branch and codebase context
already exist — the user's feedback *is* the plan.
"""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from lintel.workflows.feature_to_pr import _check_phase, _resolve_max_review_cycles
from lintel.workflows.nodes.close import close_workflow
from lintel.workflows.nodes.implement import spawn_implementation
from lintel.workflows.nodes.review import review_output
from lintel.workflows.nodes.setup_workspace import setup_workspace
from lintel.workflows.state import ThreadWorkflowState


def _change_request_review_decision(state: ThreadWorkflowState) -> str:
    """After review: approve → close, request_changes → revise (cycle-limited).

    When the circuit breaker trips, force-approves to close (so the PR is
    still pushed) rather than silently dropping.
    """
    import structlog

    _logger = structlog.get_logger()

    if state.get("error"):
        return "close"

    review_cycles = state.get("review_cycles", 0)
    max_cycles = _resolve_max_review_cycles(state)
    outputs = state.get("agent_outputs", [])

    for output in reversed(outputs):
        if not isinstance(output, dict):
            continue
        if output.get("node") != "review":
            continue
        if output.get("verdict") == "request_changes":
            if review_cycles < max_cycles:
                _logger.info(
                    "change_request_review_revise",
                    cycle=review_cycles + 1,
                    max_cycles=max_cycles,
                )
                return "revise"
            _logger.warning(
                "change_request_review_circuit_breaker_tripped",
                cycles=review_cycles,
                max_cycles=max_cycles,
            )
            return "close"
        if output.get("verdict") == "approve":
            return "close"
        break

    return "close"


def build_change_request_graph() -> StateGraph[Any]:
    """Build the change-request workflow graph.

    Flow: setup_workspace → implement → review ↔ implement (cycle) → close
    """
    graph: StateGraph[Any] = StateGraph(ThreadWorkflowState)

    graph.add_node("setup_workspace", setup_workspace)
    graph.add_node("implement", spawn_implementation)
    graph.add_node("review", review_output)
    graph.add_node("close", close_workflow)

    graph.set_entry_point("setup_workspace")
    graph.add_edge("setup_workspace", "implement")
    graph.add_conditional_edges(
        "implement",
        _check_phase,
        {"continue": "review", "close": "close"},
    )
    graph.add_conditional_edges(
        "review",
        _change_request_review_decision,
        {"close": "close", "revise": "implement"},
    )
    graph.add_edge("close", END)

    return graph
