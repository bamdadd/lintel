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


def build_approval_gate_blocks(
    gate_type: str,
    summary: str,
    callback_id: str,
    confidence: float = 0.0,
    threshold: float = 0.85,
    approval_id: str = "",
) -> list[dict[str, Any]]:
    """Build Slack Block Kit message for approval gate with confidence indicator."""
    confidence_pct = f"{confidence:.0%}"
    threshold_pct = f"{threshold:.0%}"

    # Color-code confidence: green >= threshold, yellow within 10%, red below
    if confidence >= threshold:
        conf_emoji = ":large_green_circle:"
    elif confidence >= threshold - 0.1:
        conf_emoji = ":large_yellow_circle:"
    else:
        conf_emoji = ":red_circle:"

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
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": (f"{conf_emoji} *Confidence:* {confidence_pct}"),
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Threshold:* {threshold_pct}",
                },
            ],
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": summary[:3000]},
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Approve",
                    },
                    "style": "primary",
                    "action_id": f"approval_approve_{approval_id}",
                    "value": approval_id,
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Reject",
                    },
                    "style": "danger",
                    "action_id": f"approval_reject_{approval_id}",
                    "value": approval_id,
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
