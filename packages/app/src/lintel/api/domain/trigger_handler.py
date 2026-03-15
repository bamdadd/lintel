"""TriggerHandler — maps external triggers to StartWorkflow commands."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import uuid4

from lintel.api.domain.event_dispatcher import dispatch_event_raw
from lintel.contracts.types import ThreadRef
from lintel.domain.events import TriggerFired
from lintel.workflows.commands import StartWorkflow

if TYPE_CHECKING:
    from lintel.contracts.protocols import CommandDispatcher


class TriggerHandler:
    """Maps Slack messages and webhooks to StartWorkflow commands."""

    def __init__(self, dispatcher: CommandDispatcher, app_state: Any = None) -> None:  # noqa: ANN401
        self._dispatcher = dispatcher
        self._app_state = app_state

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
        result = await self._dispatcher.dispatch(command)
        if self._app_state is not None:
            await dispatch_event_raw(
                self._app_state,
                TriggerFired(
                    payload={
                        "resource_id": thread_ts,
                        "trigger_source": "slack",
                        "workflow_type": workflow_type,
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                    }
                ),
                stream_id=f"trigger:slack:{thread_ts}",
            )
        return str(result)

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
        result = await self._dispatcher.dispatch(command)
        if self._app_state is not None:
            await dispatch_event_raw(
                self._app_state,
                TriggerFired(
                    payload={
                        "resource_id": run_ref,
                        "trigger_source": "webhook",
                        "pipeline_id": pipeline_id,
                    }
                ),
                stream_id=f"trigger:webhook:{run_ref}",
            )
        return str(result)
