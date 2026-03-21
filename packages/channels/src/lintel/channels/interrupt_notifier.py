"""Channel-agnostic interrupt notification dispatch.

Provides a single entry point for sending human interrupt notifications
across all registered channels (Slack, Telegram, etc.).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.channels.registry import ChannelRegistry
    from lintel.contracts.channel_type import ChannelType
    from lintel.workflows.types import InterruptRequest

logger = structlog.get_logger()


async def notify_interrupt(
    request: InterruptRequest,
    resume_url: str,
    channels: list[dict[str, Any]],
    channel_registry: ChannelRegistry,
) -> None:
    """Send interrupt notifications to all configured channels.

    Failures are non-fatal — each channel is attempted independently
    and errors are logged but never raised.

    Parameters
    ----------
    request:
        The InterruptRequest that was just created.
    resume_url:
        The API URL to resume the interrupt.
    channels:
        List of channel configs, each with at least
        ``{"channel_type": "slack"|"telegram", "channel_id": "..."}``.
    channel_registry:
        Registry mapping ChannelType to adapter instances.
    """
    for channel_config in channels:
        channel_type_str = channel_config.get("channel_type", "")
        channel_id = channel_config.get("channel_id", "")

        if not channel_type_str or not channel_id:
            logger.debug(
                "interrupt_notify_skipped",
                reason="missing channel_type or channel_id",
            )
            continue

        try:
            from lintel.contracts.channel_type import ChannelType

            channel_type: ChannelType = ChannelType(channel_type_str)
        except ValueError:
            logger.warning(
                "interrupt_notify_unknown_channel",
                channel_type=channel_type_str,
            )
            continue

        if not channel_registry.is_registered(channel_type):
            logger.debug(
                "interrupt_notify_skipped",
                reason="channel_not_registered",
                channel_type=channel_type_str,
            )
            continue

        try:
            adapter = channel_registry.get(channel_type)
            await _send_for_channel(
                adapter,
                channel_type,
                channel_config,
                request,
                resume_url,
            )
        except Exception:
            logger.warning(
                "interrupt_notify_failed",
                channel_type=channel_type_str,
                channel_id=channel_id,
                run_id=request.run_id,
                exc_info=True,
            )


async def _send_for_channel(
    adapter: Any,  # noqa: ANN401
    channel_type: ChannelType,
    channel_config: dict[str, Any],
    request: InterruptRequest,
    resume_url: str,
) -> None:
    """Dispatch to channel-specific notification formatter."""
    from lintel.contracts.types import ThreadRef

    thread_ref = ThreadRef(
        workspace_id=channel_config.get("workspace_id", ""),
        channel_id=channel_config["channel_id"],
        thread_ts=channel_config.get("thread_ts", ""),
    )

    interrupt_label = request.interrupt_type.value.replace("_", " ").title()
    run_short = request.run_id[:12] if request.run_id else "?"

    message = (
        f"Workflow paused \u2014 *{interrupt_label}* required\n"
        f"Run: `{run_short}` | Stage: `{request.stage}`\n"
        f"Deadline: {request.deadline.isoformat() if request.deadline else 'none'}\n"
        f"Resume: `POST {resume_url}`"
    )

    await adapter.send_message(thread_ref, message)
