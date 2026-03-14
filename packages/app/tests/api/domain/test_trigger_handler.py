"""Tests for TriggerHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock

from lintel.api.domain.trigger_handler import TriggerHandler


async def test_handle_slack_message_dispatches_start_workflow() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.return_value = "run-123"

    handler = TriggerHandler(dispatcher=dispatcher)
    result = await handler.handle_slack_message(
        workspace_id="W1",
        channel_id="C1",
        thread_ts="ts1",
        workflow_type="feature_to_pr",
    )

    assert result == "run-123"
    dispatcher.dispatch.assert_called_once()
    cmd = dispatcher.dispatch.call_args[0][0]
    assert cmd.workflow_type == "feature_to_pr"
    assert cmd.thread_ref.workspace_id == "W1"


async def test_handle_webhook_dispatches_start_workflow() -> None:
    dispatcher = AsyncMock()
    dispatcher.dispatch.return_value = "run-456"

    handler = TriggerHandler(dispatcher=dispatcher)
    result = await handler.handle_webhook(
        pipeline_id="deploy-pipeline",
        payload={"ref": "main"},
    )

    assert result == "run-456"
    dispatcher.dispatch.assert_called_once()
    cmd = dispatcher.dispatch.call_args[0][0]
    assert cmd.workflow_type == "deploy-pipeline"
    assert cmd.thread_ref.workspace_id == "system"
