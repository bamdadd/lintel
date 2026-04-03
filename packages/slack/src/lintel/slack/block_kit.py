"""Block Kit builders. Domain RichContent -> Slack Block Kit JSON."""

from __future__ import annotations

from typing import Any


def build_approval_blocks(
    gate_type: str,
    summary: str,
    callback_id: str,
) -> list[dict[str, Any]]:
    return [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"Approval Required: {gate_type}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": f"approve:{gate_type}:{callback_id}",
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": f"reject:{gate_type}:{callback_id}",
                },
            ],
        },
    ]


def build_status_blocks(
    agent_name: str,
    phase: str,
    summary: str,
    metadata: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{agent_name}* | Phase: `{phase}`",
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary[:3000]},
        },
    ]
    if metadata:
        context_elements: list[dict[str, str]] = [
            {"type": "mrkdwn", "text": f"*{k}*: {v}"} for k, v in metadata.items()
        ]
        blocks.append(
            {
                "type": "context",
                "elements": context_elements[:10],
            }
        )
    return blocks


# --- Stage status emoji mapping ---
_STATUS_EMOJI: dict[str, str] = {
    "running": ":hourglass_flowing_sand:",
    "succeeded": ":white_check_mark:",
    "failed": ":x:",
    "timed_out": ":alarm_clock:",
    "skipped": ":fast_forward:",
    "waiting_approval": ":raised_hand:",
    "approved": ":thumbsup:",
    "rejected": ":no_entry_sign:",
}


def build_stage_blocks(
    stage_name: str,
    status: str,
    run_id: str,
    duration_ms: int = 0,
    error: str = "",
    pr_url: str = "",
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a pipeline stage status update."""
    emoji = _STATUS_EMOJI.get(status, ":grey_question:")
    title = stage_name.replace("_", " ").title()
    duration_text = f" ({duration_ms / 1000:.1f}s)" if duration_ms > 0 else ""

    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{title}* — `{status}`{duration_text}",
            },
        },
    ]

    if error:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":warning: ```{error[:1500]}```",
                },
            }
        )

    if pr_url:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":link: <{pr_url}|View Pull Request>",
                },
            }
        )

    blocks.append(
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Pipeline `{run_id[:8]}`"},
            ],
        }
    )

    return blocks
