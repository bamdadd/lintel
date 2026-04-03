"""Block Kit builders. Domain RichContent -> Slack Block Kit JSON."""

from __future__ import annotations

from collections import defaultdict
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


# --- Board view ---

_COLUMN_ORDER: list[tuple[str, str, set[str]]] = [
    ("Open", ":large_blue_circle:", {"open"}),
    ("In Progress", ":hourglass_flowing_sand:", {"in_progress"}),
    ("In Review", ":eyes:", {"in_review", "approved"}),
    ("Done", ":white_check_mark:", {"merged", "closed"}),
]

_TYPE_TAG: dict[str, str] = {
    "bug": ":bug:",
    "feature": ":sparkles:",
    "refactor": ":recycle:",
    "task": ":clipboard:",
}


def build_board_blocks(
    work_items: list[dict[str, Any]],
    *,
    max_per_column: int = 5,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a kanban board view of work items."""
    if not work_items:
        return [
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": "The board is empty — no work items yet."},
            }
        ]

    by_column: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in work_items:
        status = item.get("status", "open")
        for col_name, _emoji, statuses in _COLUMN_ORDER:
            if status in statuses:
                by_column[col_name].append(item)
                break

    blocks: list[dict[str, Any]] = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Board"},
        },
    ]

    for col_name, col_emoji, _statuses in _COLUMN_ORDER:
        items = by_column.get(col_name)
        if not items:
            continue

        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{col_emoji} *{col_name}* ({len(items)})",
                },
            }
        )

        for item in items[:max_per_column]:
            title = item.get("title", "Untitled")
            wtype = item.get("work_type", "task")
            tag = _TYPE_TAG.get(wtype, ":clipboard:")
            wid = item.get("work_item_id", "")[:8]
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{tag} `{wid}` {title}",
                    },
                }
            )

        overflow = len(items) - max_per_column
        if overflow > 0:
            blocks.append(
                {
                    "type": "context",
                    "elements": [
                        {"type": "mrkdwn", "text": f"+{overflow} more"},
                    ],
                }
            )

    return blocks


# --- Modals ---

_WORK_TYPE_OPTIONS: list[dict[str, Any]] = [
    {"text": {"type": "plain_text", "text": "Feature"}, "value": "feature"},
    {"text": {"type": "plain_text", "text": "Bug"}, "value": "bug"},
    {"text": {"type": "plain_text", "text": "Task"}, "value": "task"},
    {"text": {"type": "plain_text", "text": "Refactor"}, "value": "refactor"},
]


def build_create_work_item_modal(
    *,
    callback_id: str = "create_work_item",
    private_metadata: str = "",
) -> dict[str, Any]:
    """Build a Slack modal view for creating a work item."""
    return {
        "type": "modal",
        "callback_id": callback_id,
        "private_metadata": private_metadata,
        "title": {"type": "plain_text", "text": "Create Work Item"},
        "submit": {"type": "plain_text", "text": "Create"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            {
                "type": "input",
                "block_id": "title_block",
                "label": {"type": "plain_text", "text": "Title"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "title_input",
                    "placeholder": {"type": "plain_text", "text": "e.g. Add dark mode"},
                },
            },
            {
                "type": "input",
                "block_id": "description_block",
                "optional": True,
                "label": {"type": "plain_text", "text": "Description"},
                "element": {
                    "type": "plain_text_input",
                    "action_id": "description_input",
                    "multiline": True,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "Describe the work item...",
                    },
                },
            },
            {
                "type": "input",
                "block_id": "type_block",
                "label": {"type": "plain_text", "text": "Type"},
                "element": {
                    "type": "static_select",
                    "action_id": "type_select",
                    "options": _WORK_TYPE_OPTIONS,
                    "initial_option": _WORK_TYPE_OPTIONS[0],
                },
            },
        ],
    }


def parse_view_submission(view: dict[str, Any]) -> dict[str, str]:
    """Extract field values from a Slack view_submission payload's view object.

    Returns a dict with keys: title, description, work_type.
    """
    values = view.get("state", {}).get("values", {})
    title = values.get("title_block", {}).get("title_input", {}).get("value", "") or ""
    description = (
        values.get("description_block", {}).get("description_input", {}).get("value", "") or ""
    )
    type_obj = values.get("type_block", {}).get("type_select", {}).get("selected_option")
    work_type = type_obj.get("value", "feature") if type_obj else "feature"
    return {
        "title": title,
        "description": description,
        "work_type": work_type,
    }
