"""Tests for WorkflowNode base class and migrated nodes (route, triage)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

import pytest

if TYPE_CHECKING:
    from langchain_core.runnables import RunnableConfig

    from lintel.workflows.state import ThreadWorkflowState

from lintel.workflows.base import WorkflowNode
from lintel.workflows.nodes.route import RouteIntentNode, route_intent
from lintel.workflows.nodes.triage import TriageIssueNode, triage_issue

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_state(**overrides: object) -> dict[str, object]:
    """Minimal ThreadWorkflowState dict."""
    base: dict[str, Any] = {
        "thread_ref": "ws/ch/ts",
        "correlation_id": "",
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
        "trigger_context": "",
        "run_id": "",
        "project_id": "",
        "work_item_id": "",
        "repo_url": "",
        "repo_urls": (),
        "repo_branch": "",
        "feature_branch": "",
        "credential_ids": (),
        "environment_id": "",
        "workspace_path": "",
        "workspace_paths": (),
        "research_context": "",
        "token_usage": [],
        "review_cycles": 0,
        "previous_error": "",
        "previous_failed_stage": "",
    }
    base.update(overrides)
    return base


def _make_config(**configurable: object) -> dict[str, object]:
    return {"configurable": configurable}


# ---------------------------------------------------------------------------
# WorkflowNode base class tests
# ---------------------------------------------------------------------------


class TestWorkflowNodeBase:
    """Tests for the abstract WorkflowNode base class."""

    def test_cannot_instantiate_abstract(self) -> None:
        with pytest.raises(TypeError):
            WorkflowNode(name="test")  # type: ignore[abstract]

    def test_tracker_raises_outside_execute(self) -> None:
        node = RouteIntentNode()
        with pytest.raises(RuntimeError, match="only available inside execute"):
            _ = node.tracker

    async def test_auto_mark_completed(self) -> None:
        """If execute() does not call self.complete(), __call__ auto-completes."""
        node = RouteIntentNode()
        state = _make_state(sanitized_messages=["add login feature"])
        config = _make_config()

        with patch("lintel.workflows.nodes._stage_tracking.StageTracker") as mock_cls:
            mock_tracker = mock_cls.return_value
            mock_tracker.mark_running = AsyncMock()
            mock_tracker.mark_completed = AsyncMock()

            result = await node(state, config)

        assert result["intent"] == "feature"
        mock_tracker.mark_running.assert_awaited_once_with("route")
        mock_tracker.mark_completed.assert_awaited_once_with("route")

    async def test_error_handling(self) -> None:
        """If execute() raises, the base class marks the stage as failed."""

        class FailingNode(WorkflowNode):
            name: str = "fail"

            async def execute(
                self,
                state: ThreadWorkflowState,
                config: RunnableConfig,
            ) -> dict[str, Any]:
                msg = "boom"
                raise RuntimeError(msg)

        node = FailingNode()
        config = _make_config()

        with patch("lintel.workflows.nodes._stage_tracking.StageTracker") as mock_cls:
            mock_tracker = mock_cls.return_value
            mock_tracker.mark_running = AsyncMock()
            mock_tracker.mark_completed = AsyncMock()

            result = await node(_make_state(), config)

        assert result["current_phase"] == "failed"
        assert "boom" in result["error"]
        mock_tracker.mark_completed.assert_awaited_once_with("fail", error="boom")


# ---------------------------------------------------------------------------
# RouteIntentNode tests
# ---------------------------------------------------------------------------


class TestRouteIntentNode:
    def test_is_workflow_node(self) -> None:
        assert isinstance(route_intent, WorkflowNode)

    async def test_feature_intent(self) -> None:
        node = RouteIntentNode()
        state = _make_state(sanitized_messages=["add login feature"])

        with patch("lintel.workflows.nodes._stage_tracking.StageTracker") as mock_cls:
            mock_tracker = mock_cls.return_value
            mock_tracker.mark_running = AsyncMock()
            mock_tracker.mark_completed = AsyncMock()

            result = await node(state, _make_config())

        assert result["intent"] == "feature"
        assert result["current_phase"] == "planning"

    async def test_bug_intent(self) -> None:
        node = RouteIntentNode()
        state = _make_state(sanitized_messages=["fix the broken login"])

        with patch("lintel.workflows.nodes._stage_tracking.StageTracker") as mock_cls:
            mock_tracker = mock_cls.return_value
            mock_tracker.mark_running = AsyncMock()
            mock_tracker.mark_completed = AsyncMock()

            result = await node(state, _make_config())

        assert result["intent"] == "bug"

    async def test_refactor_intent(self) -> None:
        node = RouteIntentNode()
        state = _make_state(sanitized_messages=["refactor the auth module"])

        with patch("lintel.workflows.nodes._stage_tracking.StageTracker") as mock_cls:
            mock_tracker = mock_cls.return_value
            mock_tracker.mark_running = AsyncMock()
            mock_tracker.mark_completed = AsyncMock()

            result = await node(state, _make_config())

        assert result["intent"] == "refactor"


# ---------------------------------------------------------------------------
# TriageIssueNode tests
# ---------------------------------------------------------------------------


class TestTriageIssueNode:
    def test_is_workflow_node(self) -> None:
        assert isinstance(triage_issue, WorkflowNode)

    async def test_no_runtime_fallback(self) -> None:
        node = TriageIssueNode()
        state = _make_state(sanitized_messages=["some request"])

        with patch("lintel.workflows.nodes._stage_tracking.StageTracker") as mock_cls:
            mock_tracker = mock_cls.return_value
            mock_tracker.mark_running = AsyncMock()
            mock_tracker.mark_completed = AsyncMock()
            mock_tracker.append_log = AsyncMock()

            result = await node(state, _make_config())

        assert result["intent"] == "feature"
        assert result["current_phase"] == "triaging"
        # auto-completed since no-runtime path doesn't call self.complete()
        mock_tracker.mark_completed.assert_awaited_once_with("triage")

    async def test_with_runtime(self) -> None:
        node = TriageIssueNode()

        mock_runtime = AsyncMock()
        mock_runtime.execute_step.return_value = {
            "content": '{"type": "bug", "priority": "P1", "severity": "high", "summary": "broken"}',
            "usage": {"input_tokens": 100, "output_tokens": 50},
        }

        state = _make_state(sanitized_messages=["login is broken"])
        config = _make_config(agent_runtime=mock_runtime)

        with patch("lintel.workflows.nodes._stage_tracking.StageTracker") as mock_cls:
            mock_tracker = mock_cls.return_value
            mock_tracker.mark_running = AsyncMock()
            mock_tracker.mark_completed = AsyncMock()
            mock_tracker.append_log = AsyncMock()

            result = await node(state, config)

        assert result["intent"] == "bug"
        assert result["token_usage"][0]["input_tokens"] == 100
        # complete() was called by execute, not auto-completed
        mock_tracker.mark_completed.assert_awaited_once_with(
            "triage",
            outputs={
                "token_usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
                "triage": {
                    "type": "bug",
                    "priority": "P1",
                    "severity": "high",
                    "summary": "broken",
                },
            },
            error="",
        )
