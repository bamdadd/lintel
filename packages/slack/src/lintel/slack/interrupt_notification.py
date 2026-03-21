"""Slack-specific interrupt notification formatting.

Builds Block Kit messages for human interrupt notifications and sends
them via the SlackChannelAdapter.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.types import ThreadRef
    from lintel.slack.adapter import SlackChannelAdapter
    from lintel.workflows.types import InterruptRequest


def build_interrupt_blocks(
    request: InterruptRequest,
    resume_url: str = "",
) -> list[dict[str, Any]]:
    """Build Slack Block Kit blocks for an interrupt notification.

    Parameters
    ----------
    request:
        The interrupt request that triggered the notification.
    resume_url:
        The URL users can visit to resume the interrupt.

    Returns
    -------
    list[dict]:
        Slack Block Kit blocks ready for ``blocks`` parameter.
    """
    interrupt_label = request.interrupt_type.value.replace("_", " ").title()
    run_short = request.run_id[:12] if request.run_id else "?"
    deadline_str = request.deadline.isoformat() if request.deadline else "No deadline"

    if not resume_url:
        resume_url = f"/api/v1/pipelines/{request.run_id}/stages/{request.stage}/resume"

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f":raised_hand: {interrupt_label} Required",
                "emoji": True,
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Run:*\n`{run_short}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Stage:*\n`{request.stage}`",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Type:*\n{interrupt_label}",
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Deadline:*\n{deadline_str}",
                },
            ],
        },
    ]

    # Add payload summary if present
    payload_summary = _build_payload_summary(request)
    if payload_summary:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": payload_summary,
                },
            },
        )

    # Action buttons for approval gates
    if request.interrupt_type.value == "approval_gate":
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Approve"},
                        "style": "primary",
                        "action_id": f"interrupt_approve:{request.run_id}:{request.stage}",
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reject"},
                        "style": "danger",
                        "action_id": f"interrupt_reject:{request.run_id}:{request.stage}",
                    },
                ],
            },
        )

    # Context footer
    blocks.append(
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Resume via API: `POST {resume_url}`",
                },
            ],
        },
    )

    return blocks


async def send_slack_interrupt_notification(
    adapter: SlackChannelAdapter,
    thread_ref: ThreadRef,
    request: InterruptRequest,
    resume_url: str = "",
) -> dict[str, Any]:
    """Send an interrupt notification to Slack with Block Kit formatting.

    Parameters
    ----------
    adapter:
        The Slack channel adapter to send the message through.
    thread_ref:
        Thread reference for the Slack channel/thread.
    request:
        The interrupt request that triggered the notification.
    resume_url:
        Optional resume URL override.
    """
    blocks = build_interrupt_blocks(request, resume_url)
    fallback_text = (
        f"Workflow paused — {request.interrupt_type.value} required "
        f"(run: {request.run_id[:12]}, stage: {request.stage})"
    )
    return await adapter.send_message(thread_ref, fallback_text, blocks=blocks)


def _build_payload_summary(request: InterruptRequest) -> str:
    """Extract a human-readable summary from the interrupt payload."""
    payload = request.payload
    parts: list[str] = []

    if "task_description" in payload:
        parts.append(f"*Task:* {payload['task_description']}")
    if "report_content" in payload:
        preview = str(payload["report_content"])[:200]
        if len(str(payload["report_content"])) > 200:
            preview += "..."
        parts.append(f"*Report preview:*\n```{preview}```")
    if "question" in payload:
        parts.append(f"*Question:* {payload['question']}")

    return "\n".join(parts)
