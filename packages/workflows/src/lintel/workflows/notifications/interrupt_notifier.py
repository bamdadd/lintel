"""Interrupt notification dispatch via the channels abstraction.

Sends a formatted notification when a human interrupt is created,
routing through the ``ChannelRegistry`` so Slack / Telegram / future
channels work automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.workflows.types import InterruptRequest

logger = structlog.get_logger()


async def send_interrupt_notification(
    request: InterruptRequest,
    channel_config: dict[str, Any],
    configurable: dict[str, Any],
) -> None:
    """Format and send an interrupt notification via the channels abstraction.

    Parameters
    ----------
    request:
        The InterruptRequest that was just created.
    channel_config:
        Dict with at least ``{"channel_type": "slack"|"telegram", "channel_id": "..."}``.
        Optional ``"thread_ts"`` for threaded replies.
    configurable:
        LangGraph configurable dict (used to locate the channel registry).
    """
    from lintel.contracts.channel_type import ChannelType

    channel_type_str = channel_config.get("channel_type", "slack")
    channel_id = channel_config.get("channel_id", "")
    if not channel_id:
        logger.debug("interrupt_notification_skipped", reason="no channel_id")
        return

    # Locate channel registry
    app_state = configurable.get("app_state")
    if app_state is None and request.run_id:
        from lintel.workflows.nodes._runtime_registry import get_app_state

        app_state = get_app_state(request.run_id)
    if app_state is None:
        logger.debug("interrupt_notification_skipped", reason="no app_state")
        return

    channel_registry = getattr(app_state, "channel_registry", None)
    if channel_registry is None:
        logger.debug("interrupt_notification_skipped", reason="no channel_registry")
        return

    try:
        channel_type = ChannelType(channel_type_str)
    except ValueError:
        logger.warning("interrupt_notification_unknown_channel", channel_type=channel_type_str)
        return

    if not channel_registry.is_registered(channel_type):
        logger.debug(
            "interrupt_notification_skipped",
            reason="channel_not_registered",
            channel_type=channel_type_str,
        )
        return

    adapter = channel_registry.get(channel_type)

    # Build message
    deadline_str = request.deadline.isoformat() if request.deadline else "none"
    run_short = request.run_id[:12] if request.run_id else "?"
    message = (
        f"Workflow paused — *{request.interrupt_type.value}* required\n"
        f"Run: `{run_short}` | Stage: `{request.stage}`\n"
        f"Deadline: {deadline_str}\n"
        f"Resume: `/api/v1/pipelines/{request.run_id}/stages/{request.stage}/resume`"
    )

    try:
        from lintel.contracts.types import ThreadRef

        thread_ref = ThreadRef(
            workspace_id="",
            channel_id=channel_id,
            thread_ts=channel_config.get("thread_ts", ""),
        )
        await adapter.send_message(thread_ref, message)
    except Exception:
        logger.warning(
            "interrupt_notification_send_failed",
            run_id=request.run_id,
            channel_type=channel_type_str,
        )
