"""Feature-to-PR workflow graph using LangGraph.

LangGraph is an implementation detail. This module wraps it behind
Lintel's own graph builder so the orchestration engine can be replaced.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from langgraph.graph import END, StateGraph

if TYPE_CHECKING:
    from langgraph.graph.state import CompiledStateGraph

from functools import partial

from lintel.workflows.nodes.approval_gate import approval_gate
from lintel.workflows.nodes.close import close_workflow
from lintel.workflows.nodes.implement import spawn_implementation
from lintel.workflows.nodes.ingest import ingest_message
from lintel.workflows.nodes.plan import plan_work
from lintel.workflows.nodes.research import research_codebase
from lintel.workflows.nodes.review import review_output
from lintel.workflows.nodes.route import route_intent
from lintel.workflows.nodes.setup_workspace import setup_workspace
from lintel.workflows.state import ThreadWorkflowState

MAX_REVIEW_CYCLES = 3
DEFAULT_MAX_REVIEW_CYCLES = MAX_REVIEW_CYCLES


def _resolve_max_review_cycles(state: ThreadWorkflowState) -> int:
    """Return the configured max review cycles, falling back to the default.

    Resolution order:
    1. ``max_review_cycles`` in workflow state (set from project config during setup)
    2. Module-level ``DEFAULT_MAX_REVIEW_CYCLES``
    """
    return int(state.get("max_review_cycles", DEFAULT_MAX_REVIEW_CYCLES))


def build_feature_to_pr_graph() -> StateGraph[Any]:
    """Build the feature-to-PR workflow graph."""
    graph: StateGraph[Any] = StateGraph(ThreadWorkflowState)

    graph.add_node("ingest", ingest_message)
    graph.add_node("route", route_intent)
    graph.add_node("setup_workspace", setup_workspace)
    graph.add_node("research", research_codebase)
    graph.add_node("plan", plan_work)
    graph.add_node(
        "approval_gate_research",
        partial(approval_gate, gate_type="research_approval"),
    )
    graph.add_node(
        "approval_gate_spec",
        partial(approval_gate, gate_type="spec_approval"),
    )
    graph.add_node("implement", spawn_implementation)
    graph.add_node("review", review_output)
    graph.add_node(
        "approval_gate_pr",
        partial(approval_gate, gate_type="pr_approval"),
    )
    graph.add_node("close", close_workflow)

    graph.set_entry_point("ingest")
    graph.add_edge("ingest", "route")
    graph.add_conditional_edges(
        "route",
        _route_decision,
        {
            "setup_workspace": "setup_workspace",
            "close": "close",
        },
    )
    graph.add_edge("setup_workspace", "research")
    graph.add_edge("research", "approval_gate_research")
    graph.add_edge("approval_gate_research", "plan")
    graph.add_edge("plan", "approval_gate_spec")
    graph.add_edge("approval_gate_spec", "implement")
    graph.add_conditional_edges(
        "implement",
        _check_phase,
        {"continue": "review", "close": "close"},
    )
    graph.add_conditional_edges(
        "review",
        _review_decision,
        {"continue": "approval_gate_pr", "revise": "implement", "close": "close"},
    )
    graph.add_edge("approval_gate_pr", "close")
    graph.add_edge("close", END)

    return graph


def _check_phase(state: ThreadWorkflowState) -> str:
    """Stop the pipeline if a node signals failure via error or failed verdict."""
    import structlog

    _logger = structlog.get_logger()

    if state.get("error"):
        _logger.info("check_phase_stop", reason="error", error=state.get("error"))
        return "close"
    phase = state.get("current_phase", "")
    if phase == "closed":
        _logger.info("check_phase_stop", reason="phase_closed")
        return "close"
    # Check if the last agent output has a failed verdict
    outputs = state.get("agent_outputs", [])
    for output in reversed(outputs):
        if isinstance(output, dict) and output.get("verdict") == "failed":
            _logger.info(
                "check_phase_stop",
                reason="failed_verdict",
                node=output.get("node"),
                verdict=output.get("verdict"),
            )
            return "close"
    _logger.info(
        "check_phase_continue",
        phase=phase,
        output_count=len(outputs),
    )
    return "continue"


def _review_decision(state: ThreadWorkflowState) -> str:
    """After review: approve → continue, request_changes → revise (with cycle limit).

    When the circuit breaker trips (review_cycles >= max), the pipeline
    force-approves with a warning annotation instead of closing, so a PR
    is still raised for human review.
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
                    "review_decision_revise",
                    cycle=review_cycles + 1,
                    max_cycles=max_cycles,
                )
                return "revise"
            _logger.warning(
                "review_circuit_breaker_tripped",
                cycles=review_cycles,
                max_cycles=max_cycles,
            )
            return "continue"
        if output.get("verdict") == "approve":
            return "continue"
        break

    return "continue"


def _route_decision(state: ThreadWorkflowState) -> str:
    intent = state.get("intent", "")
    if intent in ("feature", "bug", "refactor"):
        return "setup_workspace"
    return "close"


async def compile_workflow(db_url: str) -> CompiledStateGraph[Any]:
    """Compile the workflow with Postgres checkpointing."""
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(db_url) as checkpointer:
        await checkpointer.setup()

        graph = build_feature_to_pr_graph()
        return graph.compile(
            checkpointer=checkpointer,
            interrupt_before=[
                "approval_gate_research",
                "approval_gate_spec",
                "approval_gate_pr",
            ],
        )
