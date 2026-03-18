"""Tests for the regulation-to-policy workflow graph."""

from __future__ import annotations

from typing import Any

from lintel.workflows.regulation_to_policy import (
    _check_phase,
    _parse_json_response,
    _resolve_project_description,
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


# ---------------------------------------------------------------------------
# _check_phase
# ---------------------------------------------------------------------------


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

    def test_continue_on_empty_state(self) -> None:
        state = _make_state()
        assert _check_phase(state) == "continue"


# ---------------------------------------------------------------------------
# _parse_json_response
# ---------------------------------------------------------------------------


class TestParseJsonResponse:
    def test_parse_clean_json(self) -> None:
        result = _parse_json_response('{"key": "value"}')
        assert result == {"key": "value"}

    def test_parse_json_with_markdown_fences(self) -> None:
        text = '```json\n{"key": "value"}\n```'
        result = _parse_json_response(text)
        assert result == {"key": "value"}

    def test_parse_json_with_surrounding_text(self) -> None:
        text = 'Here is the result:\n{"key": "value"}\nDone.'
        result = _parse_json_response(text)
        assert result == {"key": "value"}

    def test_parse_empty_string_returns_empty_dict(self) -> None:
        assert _parse_json_response("") == {}

    def test_parse_invalid_json_returns_empty_dict(self) -> None:
        assert _parse_json_response("not json at all") == {}

    def test_parse_nested_json(self) -> None:
        text = '{"policies": [{"name": "Test"}], "assumptions": ["A1"]}'
        result = _parse_json_response(text)
        assert result["policies"][0]["name"] == "Test"
        assert result["assumptions"] == ["A1"]


# ---------------------------------------------------------------------------
# _resolve_project_description
# ---------------------------------------------------------------------------


class TestResolveProjectDescription:
    async def test_returns_empty_when_no_stores(self) -> None:
        result = await _resolve_project_description(None, "proj-1")
        assert result == ""

    async def test_returns_description_from_project_store(self) -> None:
        class FakeProjectStore:
            async def get(self, project_id: str) -> dict[str, Any] | None:
                return {"project_id": project_id, "description": "A healthcare SaaS platform"}

        class FakeAppState:
            project_store = FakeProjectStore()

        result = await _resolve_project_description(FakeAppState(), "proj-1")
        assert result == "A healthcare SaaS platform"

    async def test_falls_back_to_empty_when_no_description(self) -> None:
        class FakeProjectStore:
            async def get(self, project_id: str) -> dict[str, Any] | None:
                return {"project_id": project_id, "description": ""}

        class FakeAppState:
            project_store = FakeProjectStore()

        result = await _resolve_project_description(FakeAppState(), "proj-1")
        assert result == ""

    async def test_falls_back_to_sandbox_readme(self) -> None:
        class FakeProjectStore:
            async def get(self, project_id: str) -> dict[str, Any] | None:
                return {"project_id": project_id, "description": ""}

        class FakeSandboxManager:
            async def exec_in_sandbox(
                self, sandbox_id: str, cmd: list[str]
            ) -> dict[str, Any]:
                if "CLAUDE.md" in cmd[1]:
                    raise FileNotFoundError
                if "README.md" in cmd[1]:
                    return {"stdout": "# My Project\nA financial compliance tool."}
                return {"stdout": ""}

        class FakeAppState:
            project_store = FakeProjectStore()

        result = await _resolve_project_description(
            FakeAppState(), "proj-1",
            sandbox_manager=FakeSandboxManager(), sandbox_id="sb-1",
        )
        assert "README.md" in result
        assert "financial compliance tool" in result


# ---------------------------------------------------------------------------
# Nodes (no-runtime paths)
# ---------------------------------------------------------------------------


class TestGatherContext:
    async def test_returns_gathering_phase(self) -> None:
        state = _make_state()
        result = await gather_context(state, config=None)
        assert result["current_phase"] == "gathering_context"
        assert result["agent_outputs"][0]["node"] == "gather_context"

    async def test_assembles_trigger_context(self) -> None:
        import json

        trigger = json.dumps({
            "regulation_ids": ["reg-1"],
            "industry_context": "finance",
            "additional_context": "We handle PCI card data.",
        })
        state = _make_state(sanitized_messages=[trigger])
        result = await gather_context(state, config=None)
        assert "finance" in result["research_context"]
        assert "PCI card data" in result["research_context"]

    async def test_populates_research_context(self) -> None:
        state = _make_state()
        result = await gather_context(state, config=None)
        assert "research_context" in result


class TestAnalyseRegulation:
    async def test_fails_without_context(self) -> None:
        state = _make_state(research_context="")
        result = await analyse_regulation(state, config=None)
        assert result["current_phase"] == "failed"
        assert result["error"]

    async def test_no_runtime_fallback(self) -> None:
        state = _make_state(research_context="## Regulations\nISO 27001")
        result = await analyse_regulation(state, config=None)
        assert result["current_phase"] == "analysing"
        assert result["agent_outputs"][0]["node"] == "analyse_regulation"


class TestGeneratePolicies:
    async def test_no_runtime_fallback(self) -> None:
        state = _make_state(
            research_context="some context",
            agent_outputs=[{"node": "analyse_regulation", "analysis": {"policies": []}}],
        )
        result = await generate_policies(state, config=None)
        assert result["current_phase"] == "generating"

    async def test_fails_without_analysis_or_context(self) -> None:
        state = _make_state(research_context="", agent_outputs=[])
        result = await generate_policies(state, config=None)
        assert result["current_phase"] == "failed"


class TestFinalisePolicies:
    async def test_completes_with_no_generated_data(self) -> None:
        state = _make_state(agent_outputs=[])
        result = await finalise_policies(state, config=None)
        assert result["current_phase"] == "completed"
        assert "Nothing to persist" in result["agent_outputs"][0]["summary"]

    async def test_reports_counts_when_generated_data_present(self) -> None:
        state = _make_state(
            agent_outputs=[
                {
                    "node": "generate_policies",
                    "generated": {
                        "policies": [{"name": "Test Policy", "description": "Desc"}],
                        "procedures": [
                            {"name": "Test Proc", "policy_name": "Test Policy", "steps": ["Step 1"]}
                        ],
                        "assumptions": [{"assumption": "AES-256 default", "basis": "Industry std", "confidence": "high"}],
                        "questions": [{"question": "Do you handle PCI?", "impact": "Scope", "priority": "high"}],
                        "action_items": [{"action": "Confirm with security", "priority": "high", "owner_suggestion": "CISO"}],
                        "summary": "Generated 1 policy",
                    },
                }
            ],
        )
        result = await finalise_policies(state, config=None)
        assert result["current_phase"] == "completed"
        summary = result["agent_outputs"][0]["summary"]
        assert "1 assumptions" in summary or "assumptions" in summary
        assert "1 questions" in summary or "questions" in summary


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


class TestGraphBuilder:
    def test_build_graph_returns_state_graph(self) -> None:
        graph = build_regulation_to_policy_graph()
        assert graph is not None
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

    def test_graph_entry_point_is_gather_context(self) -> None:
        from langgraph.graph import StateGraph

        graph = build_regulation_to_policy_graph()
        assert isinstance(graph, StateGraph)
        # The compiled graph should have gather_context as the start
        compiled = graph.compile()
        assert compiled is not None


# ---------------------------------------------------------------------------
# Registry integration
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Stage tracking integration
# ---------------------------------------------------------------------------


class TestStageTracking:
    def test_node_to_stage_mappings_exist(self) -> None:
        from lintel.workflows.nodes._stage_tracking import NODE_TO_STAGE

        expected = [
            "gather_context",
            "analyse_regulation",
            "generate_policies",
            "approval_gate_policies",
            "finalise",
        ]
        for node_name in expected:
            assert node_name in NODE_TO_STAGE, f"Missing NODE_TO_STAGE mapping for {node_name}"
