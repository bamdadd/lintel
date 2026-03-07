"""TriggerHandler — maps external triggers to StartWorkflow commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.contracts.commands import StartWorkflow
from lintel.contracts.types import ThreadRef

if TYPE_CHECKING:
    from lintel.contracts.protocols import CommandDispatcher


class TriggerHandler:
    """Maps Slack messages and webhooks to StartWorkflow commands."""

    def __init__(self, dispatcher: CommandDispatcher) -> None:
        self._dispatcher = dispatcher

    async def handle_slack_message(
        self,
        workspace_id: str,
        channel_id: str,
        thread_ts: str,
        workflow_type: str,
    ) -> str:
        command = StartWorkflow(
            thread_ref=ThreadRef(
                workspace_id=workspace_id,
                channel_id=channel_id,
                thread_ts=thread_ts,
            ),
            workflow_type=workflow_type,
        )
        return await self._dispatcher.dispatch(command)

    async def handle_webhook(
        self,
        pipeline_id: str,
        payload: dict[str, Any],
    ) -> str:
        run_ref = f"webhook:{pipeline_id}:{uuid4().hex[:8]}"
        command = StartWorkflow(
            thread_ref=ThreadRef(
                workspace_id="system",
                channel_id=pipeline_id,
                thread_ts=run_ref,
            ),
            workflow_type=pipeline_id,
        )
        return await self._dispatcher.dispatch(command)
