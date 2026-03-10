"""Tests for the feature-to-PR workflow graph."""

from __future__ import annotations

from typing import Any

from lintel.workflows.feature_to_pr import (
    _route_decision,
    build_feature_to_pr_graph,
)
from lintel.workflows.state import ThreadWorkflowState


class TestRouteDecision:
    """Tests for the route decision function."""

    def test_feature_intent_routes_to_plan(self) -> None:
        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="planning",
            sanitized_messages=[],
            intent="feature",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        assert _route_decision(state) == "setup_workspace"

    def test_bug_intent_routes_to_plan(self) -> None:
        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="planning",
            sanitized_messages=[],
            intent="bug",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        assert _route_decision(state) == "setup_workspace"

    def test_refactor_intent_routes_to_plan(self) -> None:
        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="planning",
            sanitized_messages=[],
            intent="refactor",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        assert _route_decision(state) == "setup_workspace"

    def test_unknown_intent_routes_to_close(self) -> None:
        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="planning",
            sanitized_messages=[],
            intent="chat",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        assert _route_decision(state) == "close"

    def test_empty_intent_routes_to_close(self) -> None:
        state: dict[str, Any] = {"intent": ""}
        assert _route_decision(state) == "close"  # type: ignore[arg-type]


class TestGraphStructure:
    """Tests for graph node and edge configuration."""

    def test_graph_has_expected_nodes(self) -> None:
        graph = build_feature_to_pr_graph()
        expected_nodes = {
            "ingest",
            "route",
            "setup_workspace",
            "research",
            "approval_gate_research",
            "plan",
            "approval_gate_spec",
            "implement",
            "review",
            "approval_gate_pr",
            "close",
        }
        # LangGraph stores nodes in the graph builder's _nodes dict
        assert set(graph.nodes) == expected_nodes

    def test_graph_entry_point_is_ingest(self) -> None:
        graph = build_feature_to_pr_graph()
        compiled = graph.compile()
        draw = compiled.get_graph()
        # __start__ node should have an edge to "ingest"
        start_edges = [e for e in draw.edges if e.source == "__start__"]
        assert len(start_edges) == 1
        assert start_edges[0].target == "ingest"


class TestNodeFunctions:
    """Tests for individual workflow node functions."""

    async def test_ingest_sets_phase(self) -> None:
        from lintel.workflows.nodes.ingest import ingest_message

        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="",
            sanitized_messages=["hello"],
            intent="",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        result = await ingest_message(state)
        assert result["current_phase"] == "ingesting"

    async def test_route_classifies_bug(self) -> None:
        from lintel.workflows.nodes.route import route_intent

        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="",
            sanitized_messages=["there is a bug in the login"],
            intent="",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        result = await route_intent(state)
        assert result["intent"] == "bug"

    async def test_route_classifies_refactor(self) -> None:
        from lintel.workflows.nodes.route import route_intent

        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="",
            sanitized_messages=["refactor the auth module"],
            intent="",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        result = await route_intent(state)
        assert result["intent"] == "refactor"

    async def test_route_defaults_to_feature(self) -> None:
        from lintel.workflows.nodes.route import route_intent

        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="",
            sanitized_messages=["add a new dashboard"],
            intent="",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        result = await route_intent(state)
        assert result["intent"] == "feature"

    async def test_plan_produces_tasks(self) -> None:
        from lintel.workflows.nodes.plan import plan_work

        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="",
            sanitized_messages=[],
            intent="feature",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        result = await plan_work(state, {"configurable": {}})
        assert "plan" in result
        assert len(result["plan"]["tasks"]) > 0

    async def test_implement_returns_error_without_sandbox(self) -> None:
        from lintel.workflows.nodes.implement import spawn_implementation
        from tests.unit.workflows.test_implement_node import DummySandboxManager

        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="",
            sanitized_messages=[],
            intent="feature",
            plan={"tasks": ["task1"]},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_id=None,
            sandbox_results=[],
            pr_url="",
            error=None,
        )
        result = await spawn_implementation(
            state, {"configurable": {"sandbox_manager": DummySandboxManager()}}
        )
        assert result["error"] is not None

    async def test_review_produces_agent_output(self) -> None:
        from lintel.workflows.nodes.review import review_output

        state = ThreadWorkflowState(
            thread_ref="thread:w:c:t",
            correlation_id="abc",
            current_phase="",
            sanitized_messages=[],
            intent="feature",
            plan={},
            agent_outputs=[],
            pending_approvals=[],
            sandbox_results=[{"diff": "some diff content"}],
            pr_url="",
            error=None,
        )
        result = await review_output(state)
        assert len(result["agent_outputs"]) > 0
        assert result["agent_outputs"][0]["node"] == "review"
