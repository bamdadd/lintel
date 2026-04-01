"""Slack approval notification handler (REQ-017).

Subscribes to ApprovalRequested events and sends Slack interactive
messages via the SlackChannelAdapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from lintel.slack.block_kit import build_approval_gate_blocks

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.slack.adapter import SlackChannelAdapter

logger = structlog.get_logger()


class ApprovalNotificationHandler:
    """Handles ApprovalRequested events by sending Slack notifications."""

    def __init__(
        self,
        adapter: SlackChannelAdapter,
        *,
        default_channel: str = "",
    ) -> None:
        self._adapter = adapter
        self._default_channel = default_channel

    async def handle(self, event: EventEnvelope) -> None:
        """Send a Slack approval notification for an ApprovalRequested event."""
        if event.event_type != "HumanInterruptRequested":
            return

        payload = event.payload or {}
        interrupt_type = payload.get("interrupt_type", "")
        if interrupt_type != "approval_gate":
            return

        approval_id = payload.get("interrupt_id", "")
        run_id = payload.get("run_id", "")
        stage = payload.get("stage", "")
        confidence = float(payload.get("confidence", 0.0))
        threshold = float(payload.get("threshold", 0.85))

        # Determine channel — use thread_ref if available, else default
        channel = self._default_channel
        thread_ref = event.thread_ref
        if thread_ref and thread_ref.channel_id:
            channel = thread_ref.channel_id

        if not channel:
            logger.warning(
                "approval_notification_no_channel",
                approval_id=approval_id,
                run_id=run_id,
            )
            return

        summary = (
            f"*Run:* `{run_id[:8]}...`\n"
            f"*Stage:* `{stage}`\n"
            f"Review required — confidence below threshold."
        )

        blocks = build_approval_gate_blocks(
            gate_type=stage,
            summary=summary,
            callback_id=f"approval:{approval_id}",
            confidence=confidence,
            threshold=threshold,
            approval_id=approval_id,
        )

        try:
            thread_ts = thread_ref.thread_ts if thread_ref and thread_ref.thread_ts else None
            await self._adapter.send_message(
                channel_id=channel,
                thread_ts=thread_ts or "",
                text=f"Approval required for {stage}",
                blocks=blocks,
            )
            logger.info(
                "approval_notification_sent",
                approval_id=approval_id,
                channel=channel,
            )
        except Exception:
            logger.warning(
                "approval_notification_failed",
                approval_id=approval_id,
                channel=channel,
                exc_info=True,
            )
