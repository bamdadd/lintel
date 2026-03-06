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
