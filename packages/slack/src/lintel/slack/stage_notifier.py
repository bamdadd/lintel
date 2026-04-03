"""Pipeline stage → Slack thread notifier.

Subscribes to pipeline stage events and posts Block Kit status updates
to the originating Slack thread.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

from lintel.slack.block_kit import build_stage_blocks

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.types import ThreadRef

logger = structlog.get_logger()


class ChannelAdapter(Protocol):
    """Minimal adapter protocol for posting messages."""

    async def send_message(
        self, thread_ref: ThreadRef, text: str, **kwargs: object
    ) -> dict[str, Any]: ...


class PipelineRunLookup(Protocol):
    """Protocol for resolving a run_id to its originating thread_ref."""

    async def get_thread_ref(self, run_id: str) -> ThreadRef | None: ...


class PipelineStageNotifier:
    """Posts pipeline stage status updates to Slack threads.

    Designed to be wired as an EventBus subscriber. Call ``handle()``
    with any pipeline stage event that has ``run_id`` in its payload.
    """

    def __init__(
        self,
        adapter: ChannelAdapter,
        run_lookup: PipelineRunLookup,
    ) -> None:
        self._adapter = adapter
        self._run_lookup = run_lookup

    async def handle(self, event: EventEnvelope) -> None:
        """Handle a pipeline stage event by posting to the Slack thread."""
        run_id = event.payload.get("run_id", "")
        if not run_id:
            logger.debug("stage_notify_skip_no_run_id", event_type=event.event_type)
            return

        thread_ref = await self._run_lookup.get_thread_ref(str(run_id))
        if thread_ref is None:
            logger.debug("stage_notify_skip_no_thread", run_id=run_id)
            return

        stage_name = str(event.payload.get("node_name", event.payload.get("stage_name", "")))
        status = _status_from_event_type(event.event_type)
        duration_ms = int(event.payload.get("timestamp_ms", 0))
        error = str(event.payload.get("error", ""))
        pr_url = str(event.payload.get("pr_url", ""))

        blocks = build_stage_blocks(
            stage_name=stage_name,
            status=status,
            run_id=str(run_id),
            duration_ms=duration_ms,
            error=error,
            pr_url=pr_url,
        )
        fallback = f"{stage_name}: {status}"

        try:
            await self._adapter.send_message(thread_ref, fallback, blocks=blocks)
            logger.info(
                "stage_notify_sent",
                run_id=run_id,
                stage=stage_name,
                status=status,
            )
        except Exception:
            logger.warning(
                "stage_notify_failed",
                run_id=run_id,
                stage=stage_name,
                exc_info=True,
            )


# Event types that this notifier handles
STAGE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        "PipelineStageCompleted",
        "PipelineStageApproved",
        "PipelineStageRejected",
        "PipelineStageRetried",
        "PipelineStageAutoRetried",
        "PipelineStageTimedOut",
        "PipelineRunStarted",
        "PipelineRunCompleted",
        "PipelineRunFailed",
    }
)


def _status_from_event_type(event_type: str) -> str:
    """Map event type to a human-readable stage status."""
    mapping: dict[str, str] = {
        "PipelineStageCompleted": "succeeded",
        "PipelineStageApproved": "approved",
        "PipelineStageRejected": "rejected",
        "PipelineStageRetried": "running",
        "PipelineStageAutoRetried": "running",
        "PipelineStageTimedOut": "timed_out",
        "PipelineRunStarted": "running",
        "PipelineRunCompleted": "succeeded",
        "PipelineRunFailed": "failed",
    }
    return mapping.get(event_type, "unknown")
