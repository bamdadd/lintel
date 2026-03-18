"""Tests for the regulation-to-policy workflow graph."""

from __future__ import annotations

from typing import Any

from lintel.workflows.regulation_to_policy import (
    _check_phase,
    analyse_regulation,
    build_regulation_to_policy_graph,
    finalise_policies,
    gather_context,
    generate_policies,
)


def _make_state(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "thread_ref": "ws/ch/ts",
        "correlation_id": "corr-1",
        "current_phase": "",
        "sanitized_messages": [],
        "intent": "",
        "plan": {},
        "agent_outputs": [],
        "pending_approvals": [],
        "sandbox_id": None,
        "sandbox_results": [],
        "pr_url": "",
        "error": None,
        "run_id": "run-1",
        "project_id": "proj-1",
        "work_item_id": "",
        "repo_url": "",
        "repo_urls": (),
        "repo_branch": "main",
        "feature_branch": "",
        "credential_ids": (),
        "environment_id": "",
        "workspace_path": "",
        "research_context": "",
        "token_usage": [],
        "review_cycles": 0,
        "previous_error": "",
        "previous_failed_stage": "",
    }
    base.update(overrides)
    return base


class TestCheckPhase:
    def test_continue_on_normal_state(self) -> None:
        state = _make_state(current_phase="generating")
        assert _check_phase(state) == "continue"

    def test_close_on_error(self) -> None:
        state = _make_state(error="Something went wrong")
        assert _check_phase(state) == "close"

    def test_close_on_closed_phase(self) -> None:
        state = _make_state(current_phase="closed")
        assert _check_phase(state) == "close"

    def test_close_on_failed_phase(self) -> None:
        state = _make_state(current_phase="failed")
        assert _check_phase(state) == "close"

    def test_close_on_failed_verdict(self) -> None:
        state = _make_state(
            agent_outputs=[{"node": "analyse", "verdict": "failed"}],
        )
        assert _check_phase(state) == "close"


class TestNodes:
    async def test_gather_context(self) -> None:
        state = _make_state()
        result = await gather_context(state)
        assert result["current_phase"] == "gathering_context"
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["node"] == "gather_context"

    async def test_analyse_regulation(self) -> None:
        state = _make_state()
        result = await analyse_regulation(state)
        assert result["current_phase"] == "analysing"
        assert result["agent_outputs"][0]["node"] == "analyse_regulation"

    async def test_generate_policies(self) -> None:
        state = _make_state()
        result = await generate_policies(state)
        assert result["current_phase"] == "generating"
        assert result["agent_outputs"][0]["node"] == "generate_policies"

    async def test_finalise_policies(self) -> None:
        state = _make_state()
        result = await finalise_policies(state)
        assert result["current_phase"] == "completed"
        assert result["agent_outputs"][0]["node"] == "finalise"


class TestGraphBuilder:
    def test_build_graph_returns_state_graph(self) -> None:
        graph = build_regulation_to_policy_graph()
        assert graph is not None
        # Should have the expected nodes
        node_names = set(graph.nodes.keys())
        assert "gather_context" in node_names
        assert "analyse_regulation" in node_names
        assert "generate_policies" in node_names
        assert "approval_gate_policies" in node_names
        assert "finalise" in node_names
        assert "close" in node_names

    def test_graph_compiles(self) -> None:
        graph = build_regulation_to_policy_graph()
        compiled = graph.compile()
        assert compiled is not None


class TestRegistryIntegration:
    def test_regulation_to_policy_in_registry(self) -> None:
        from lintel.workflows.registry import WORKFLOW_BUILDERS

        assert "regulation_to_policy" in WORKFLOW_BUILDERS

    def test_get_workflow_builder(self) -> None:
        from lintel.workflows.registry import get_workflow_builder

        builder = get_workflow_builder("regulation_to_policy")
        assert builder is not None
        graph = builder()
        assert graph is not None
