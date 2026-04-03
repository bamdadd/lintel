"""Slack slash command parsing and response builders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SlashCommand:
    """Parsed slash command."""

    subcommand: str
    args: str = ""


def parse_slash_command(text: str) -> SlashCommand:
    """Parse a /lintel slash command text into subcommand and args.

    Accepts both '/lintel board' and bare 'board' (Slack sends just the text after /lintel).
    """
    cleaned = text.strip()
    if cleaned.startswith("/lintel"):
        cleaned = cleaned[len("/lintel") :].strip()

    if not cleaned:
        return SlashCommand(subcommand="help")

    parts = cleaned.split(None, 1)
    subcommand = parts[0].lower()
    args = parts[1].strip() if len(parts) > 1 else ""
    return SlashCommand(subcommand=subcommand, args=args)


def build_help_response() -> list[dict[str, Any]]:
    """Build Block Kit blocks listing available slash commands."""
    commands = [
        ("`/lintel board`", "Show kanban board summary"),
        ("`/lintel status [WORK-ID]`", "Check work item or pipeline status"),
        ("`/lintel create [story|bug|task] <title>`", "Create a new work item"),
        ("`/lintel help`", "Show this help message"),
    ]

    lines = "\n".join(f"- {cmd} -- {desc}" for cmd, desc in commands)

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "Lintel Commands"},
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": lines},
        },
    ]


def build_status_response(
    work_item: dict[str, Any] | None,
    work_item_id: str,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks for a work item status query."""
    if work_item is None:
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Work item `{work_item_id}` not found.",
                },
            }
        ]

    title = work_item.get("title", "Untitled")
    status = work_item.get("status", "unknown")
    wtype = work_item.get("work_type", "task")
    wid = work_item.get("work_item_id", "")[:12]
    pr_url = work_item.get("pr_url", "")

    status_text = f"*{title}*\n`{wid}` | Status: `{status}` | Type: `{wtype}`"
    if pr_url:
        status_text += f"\n<{pr_url}|View PR>"

    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": status_text},
        },
    ]


def build_create_response(
    title: str,
    work_type: str,
    work_item_id: str,
) -> list[dict[str, Any]]:
    """Build Block Kit blocks confirming work item creation."""
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f":white_check_mark: Created `{work_type}`: *{title}*\nID: `{work_item_id}`"
                ),
            },
        },
    ]


def build_error_response(message: str) -> list[dict[str, Any]]:
    """Build Block Kit blocks for an error message."""
    return [
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f":warning: {message}"},
        },
    ]
