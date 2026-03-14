"""Tests for policy enforcement in workflow executor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lintel.contracts.types import PolicyAction
from lintel.domain.workflow_executor import WorkflowExecutor


@pytest.fixture()
def executor() -> WorkflowExecutor:
    event_store = AsyncMock()
    event_store.append = AsyncMock()
    app_state = MagicMock()
    app_state.pipeline_store = AsyncMock()
    app_state.policy_store = AsyncMock()
    app_state.approval_request_store = AsyncMock()
    app_state.chat_store = AsyncMock()
    app_state.projection_engine = None
    return WorkflowExecutor(
        event_store=event_store,
        app_state=app_state,
    )


class TestPolicyEvaluation:
    async def test_evaluate_policy_returns_require_approval_by_default(
        self,
        executor: WorkflowExecutor,
    ) -> None:
        """Default policy when no policies are configured."""
        executor._app_state.policy_store.list_all = AsyncMock(return_value=[])
        result = await executor._evaluate_policy("run-1", "approval_gate_spec")
        assert result == "require_approval"

    async def test_evaluate_policy_returns_auto_approve(
        self,
        executor: WorkflowExecutor,
    ) -> None:
        """Policy with auto_approve action."""
        from lintel.contracts.types import Policy

        policy = Policy(
            policy_id="p1",
            name="Auto approve specs",
            event_type="approve_spec",
            condition="",
            action=PolicyAction.AUTO_APPROVE,
            approvers=(),
            project_id="",
        )
        executor._app_state.policy_store.list_all = AsyncMock(return_value=[policy])
        executor._app_state.pipeline_store.get = AsyncMock(return_value=None)

        with patch(
            "lintel.workflows.nodes._stage_tracking.NODE_TO_STAGE",
            {"approval_gate_spec": "approve_spec"},
        ):
            result = await executor._evaluate_policy("run-1", "approval_gate_spec")
        assert result == "auto_approve"

    async def test_evaluate_policy_returns_block(
        self,
        executor: WorkflowExecutor,
    ) -> None:
        """Policy with block action."""
        from lintel.contracts.types import Policy

        policy = Policy(
            policy_id="p1",
            name="Block merges",
            event_type="approved_for_pr",
            condition="",
            action=PolicyAction.BLOCK,
            approvers=(),
            project_id="",
        )
        executor._app_state.policy_store.list_all = AsyncMock(return_value=[policy])
        executor._app_state.pipeline_store.get = AsyncMock(return_value=None)

        with patch(
            "lintel.workflows.nodes._stage_tracking.NODE_TO_STAGE",
            {"approval_gate_pr": "approved_for_pr"},
        ):
            result = await executor._evaluate_policy("run-1", "approval_gate_pr")
        assert result == "block"

    async def test_evaluate_policy_handles_exception(
        self,
        executor: WorkflowExecutor,
    ) -> None:
        """Falls back to require_approval on error."""
        executor._app_state.policy_store.list_all = AsyncMock(
            side_effect=RuntimeError("boom"),
        )
        result = await executor._evaluate_policy("run-1", "some_gate")
        assert result == "require_approval"

    async def test_evaluate_policy_no_app_state(self) -> None:
        """No app state returns default."""
        executor = WorkflowExecutor(event_store=AsyncMock(), app_state=None)
        result = await executor._evaluate_policy("run-1", "gate")
        assert result == "require_approval"
