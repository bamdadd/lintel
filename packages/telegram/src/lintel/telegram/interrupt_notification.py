"""Telegram-specific interrupt notification formatting.

Builds inline keyboard and HTML-formatted messages for human interrupt
notifications and sends them via the TelegramChannelAdapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef
    from lintel.telegram.adapter import TelegramChannelAdapter
    from lintel.workflows.types import InterruptRequest


def build_interrupt_message(
    request: InterruptRequest,
    resume_url: str = "",
) -> str:
    """Build an HTML-formatted message for a Telegram interrupt notification.

    Parameters
    ----------
    request:
        The interrupt request that triggered the notification.
    resume_url:
        The URL users can visit to resume the interrupt.

    Returns
    -------
    str:
        HTML-formatted message text.
    """
    interrupt_label = request.interrupt_type.value.replace("_", " ").title()
    run_short = request.run_id[:12] if request.run_id else "?"
    deadline_str = request.deadline.isoformat() if request.deadline else "No deadline"

    if not resume_url:
        resume_url = f"/api/v1/pipelines/{request.run_id}/stages/{request.stage}/resume"

    lines = [
        f"<b>Workflow Paused — {interrupt_label} Required</b>",
        "",
        f"<b>Run:</b> <code>{run_short}</code>",
        f"<b>Stage:</b> <code>{request.stage}</code>",
        f"<b>Type:</b> {interrupt_label}",
        f"<b>Deadline:</b> {deadline_str}",
    ]

    # Payload summary
    payload = request.payload
    if "task_description" in payload:
        lines.extend(["", f"<b>Task:</b> {payload['task_description']}"])
    if "report_content" in payload:
        preview = str(payload["report_content"])[:200]
        if len(str(payload["report_content"])) > 200:
            preview += "..."
        lines.extend(["", "<b>Report preview:</b>", f"<pre>{preview}</pre>"])
    if "question" in payload:
        lines.extend(["", f"<b>Question:</b> {payload['question']}"])

    lines.extend(
        [
            "",
            f"<b>Resume:</b> <code>POST {resume_url}</code>",
        ]
    )

    return "\n".join(lines)


def build_interrupt_keyboard(
    request: InterruptRequest,
) -> dict[str, Any]:
    """Build an inline keyboard for approval gate interrupts.

    Parameters
    ----------
    request:
        The interrupt request.

    Returns
    -------
    dict:
        Telegram InlineKeyboardMarkup for ``reply_markup`` parameter.
    """
    if request.interrupt_type.value != "approval_gate":
        return {}

    # Truncate callback data to stay under Telegram's 64-byte limit
    run_short = request.run_id[:20]
    stage_short = request.stage[:20]

    return {
        "inline_keyboard": [
            [
                {
                    "text": "Approve",
                    "callback_data": f"ia:{run_short}:{stage_short}",
                },
                {
                    "text": "Reject",
                    "callback_data": f"ir:{run_short}:{stage_short}",
                },
            ],
        ],
    }


async def send_telegram_interrupt_notification(
    adapter: TelegramChannelAdapter,
    thread_ref: ThreadRef,
    request: InterruptRequest,
    resume_url: str = "",
) -> dict[str, Any]:
    """Send an interrupt notification to Telegram with inline keyboard.

    Parameters
    ----------
    adapter:
        The Telegram channel adapter to send the message through.
    thread_ref:
        Thread reference for the Telegram chat/thread.
    request:
        The interrupt request that triggered the notification.
    resume_url:
        Optional resume URL override.
    """
    message = build_interrupt_message(request, resume_url)
    keyboard = build_interrupt_keyboard(request)

    kwargs: dict[str, Any] = {}
    if keyboard:
        kwargs["reply_markup"] = keyboard

    return await adapter.send_message(thread_ref, message, **kwargs)
