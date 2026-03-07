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
from lintel.workflows.nodes.implement import spawn_implementation
from lintel.workflows.nodes.ingest import ingest_message
from lintel.workflows.nodes.plan import plan_work
from lintel.workflows.nodes.review import review_output
from lintel.workflows.nodes.route import route_intent
from lintel.workflows.nodes.setup_workspace import setup_workspace
from lintel.workflows.nodes.test_code import run_tests
from lintel.workflows.state import ThreadWorkflowState


def build_feature_to_pr_graph() -> StateGraph[Any]:
    """Build the feature-to-PR workflow graph."""
    graph: StateGraph[Any] = StateGraph(ThreadWorkflowState)

    graph.add_node("ingest", ingest_message)
    graph.add_node("route", route_intent)
    graph.add_node("setup_workspace", setup_workspace)  # type: ignore[arg-type]
    graph.add_node("plan", plan_work)
    graph.add_node(
        "approval_gate_spec",
        partial(approval_gate, gate_type="spec_approval"),
    )
    graph.add_node("implement", spawn_implementation)  # type: ignore[arg-type]
    graph.add_node("test", run_tests)  # type: ignore[arg-type]
    graph.add_node("review", review_output)  # type: ignore[arg-type]
    graph.add_node(
        "approval_gate_merge",
        partial(approval_gate, gate_type="merge_approval"),
    )
    graph.add_node("close", lambda s: {**s, "current_phase": "closed"})

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
    graph.add_edge("setup_workspace", "plan")
    graph.add_edge("plan", "approval_gate_spec")
    graph.add_edge("approval_gate_spec", "implement")
    graph.add_edge("implement", "test")
    graph.add_edge("test", "review")
    graph.add_edge("review", "approval_gate_merge")
    graph.add_edge("approval_gate_merge", "close")
    graph.add_edge("close", END)

    return graph


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
            interrupt_before=["approval_gate_spec", "approval_gate_merge"],
        )
