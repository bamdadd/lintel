"""Tests for workflow nodes: ingest, route, review, research, triage, test_code, generic."""

from __future__ import annotations

from typing import Any

from lintel.workflows.nodes.generic import _stub
from lintel.workflows.nodes.ingest import ingest_message
from lintel.workflows.nodes.research import research_codebase
from lintel.workflows.nodes.review import review_output
from lintel.workflows.nodes.route import route_intent
from lintel.workflows.nodes.test_code import run_tests
from lintel.workflows.nodes.triage import triage_issue


class TestIngestNode:
    async def test_returns_current_phase(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["hello"]}
        result = await ingest_message(state)  # type: ignore[arg-type]
        assert result["current_phase"] == "ingesting"

    async def test_passes_through_sanitized_messages(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["msg1", "msg2"]}
        result = await ingest_message(state)  # type: ignore[arg-type]
        assert result["sanitized_messages"] == ["msg1", "msg2"]

    async def test_empty_messages(self) -> None:
        state: dict[str, Any] = {}
        result = await ingest_message(state)  # type: ignore[arg-type]
        assert result["sanitized_messages"] == []


class TestRouteNode:
    async def test_detects_bug_intent(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["there is a bug in login"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "bug"

    async def test_detects_refactor_intent(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["refactor the database module"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "refactor"

    async def test_defaults_to_feature(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["add a new dashboard page"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "feature"

    async def test_sets_phase_to_planning(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["anything"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["current_phase"] == "planning"

    async def test_error_keyword_detected(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["error in production"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "bug"

    async def test_clean_keyword_triggers_refactor(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": ["clean up this module"]}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "refactor"

    async def test_empty_messages(self) -> None:
        state: dict[str, Any] = {"sanitized_messages": []}
        result = await route_intent(state)  # type: ignore[arg-type]
        assert result["intent"] == "feature"


class TestReviewNode:
    async def test_request_changes_sets_implementing_phase(self) -> None:
        """Without agent runtime, verdict defaults to request_changes → implementing."""
        state: dict[str, Any] = {"sandbox_results": [{"diff": "some changes"}]}
        result = await review_output(state)  # type: ignore[arg-type]
        assert result["current_phase"] == "implementing"
        assert result["review_cycles"] == 1

    async def test_approve_sets_pr_approval_phase(self) -> None:
        """No changes to review → auto-approve → awaiting_pr_approval."""
        state: dict[str, Any] = {"sandbox_results": []}
        result = await review_output(state)  # type: ignore[arg-type]
        assert result["current_phase"] == "awaiting_pr_approval"

    async def test_produces_agent_output(self) -> None:
        state: dict[str, Any] = {"sandbox_results": [{"diff": "some changes"}]}
        result = await review_output(state)  # type: ignore[arg-type]
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["node"] == "review"


class TestResearchNode:
    async def test_proceeds_without_sandbox_when_runtime_missing(self) -> None:
        """Research node returns empty context when no sandbox and no runtime."""
        import unittest.mock

        state: dict[str, Any] = {
            "sandbox_id": None,
            "sanitized_messages": ["test request"],
        }
        config: dict[str, Any] = {"configurable": {}}

        with (
            unittest.mock.patch(
                "lintel.workflows.nodes._stage_tracking.mark_running",
                unittest.mock.AsyncMock(),
            ),
            unittest.mock.patch(
                "lintel.workflows.nodes._stage_tracking.append_log",
                unittest.mock.AsyncMock(),
            ),
            unittest.mock.patch(
                "lintel.workflows.nodes._stage_tracking.mark_completed",
                unittest.mock.AsyncMock(),
            ),
        ):
            result = await research_codebase(state, config)  # type: ignore[arg-type]
        assert result["current_phase"] == "planning"
        assert result["research_context"] == ""


class TestTriageNode:
    async def test_returns_classification(self) -> None:
        state: dict = {"sanitized_messages": ["fix the bug"], "thread_ref": "W1/C1/t1"}
        config: dict = {"configurable": {}}
        result = await triage_issue(state, config)
        assert result["current_phase"] == "triaging"
        assert result["intent"] == "feature"


class TestRunTestsNode:
    async def test_skips_without_sandbox(self) -> None:
        result = await run_tests({})  # type: ignore[arg-type]
        assert result["current_phase"] == "reviewing"
        assert result["agent_outputs"][0]["verdict"] == "skipped"


class TestStubFactory:
    def test_stub_creates_named_function(self) -> None:
        node = _stub("my_node", "my_phase", "my summary")
        assert node.__name__ == "my_node"

    async def test_stub_returns_correct_state(self) -> None:
        node = _stub("test_node", "testing_phase", "test summary")
        result = await node({})
        assert result["current_phase"] == "testing_phase"
        assert result["agent_outputs"][0]["node"] == "test_node"
        assert result["agent_outputs"][0]["summary"] == "test summary"
