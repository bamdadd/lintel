"""Translate Slack events to Lintel domain commands."""

from __future__ import annotations

from lintel.contracts.commands import (
    GrantApproval,
    ProcessIncomingMessage,
    RejectApproval,
)
from typing import Any

from lintel.contracts.types import ThreadRef


def translate_message_event(
    event: dict[str, Any],
) -> ProcessIncomingMessage | None:
    """Translate a Slack message event to a ProcessIncomingMessage command."""
    if event.get("bot_id") or event.get("subtype"):
        return None

    thread_ts = event.get("thread_ts", event.get("ts", ""))
    channel_id = event.get("channel", "")
    team_id = event.get("team", "")

    if not all([thread_ts, channel_id, team_id]):
        return None

    return ProcessIncomingMessage(
        thread_ref=ThreadRef(
            workspace_id=team_id,
            channel_id=channel_id,
            thread_ts=thread_ts,
        ),
        raw_text=event.get("text", ""),
        sender_id=event.get("user", ""),
        sender_name="",
    )


def translate_approval_action(
    body: dict[str, Any],
) -> GrantApproval | RejectApproval | None:
    """Translate a Slack interactive action to an approval command."""
    actions = body.get("actions", [])
    if not actions:
        return None

    action = actions[0]
    action_id = action.get("action_id", "")
    user = body.get("user", {})

    # Parse action_id: "approve:{gate_type}:{thread_ref}"
    parts = action_id.split(":", 2)
    if len(parts) < 3:
        return None

    decision, gate_type, thread_ref_str = parts
    ref_parts = thread_ref_str.split(":")
    if len(ref_parts) < 4:
        return None

    thread_ref = ThreadRef(
        workspace_id=ref_parts[1],
        channel_id=ref_parts[2],
        thread_ts=ref_parts[3],
    )

    if decision == "approve":
        return GrantApproval(
            thread_ref=thread_ref,
            gate_type=gate_type,
            approver_id=user.get("id", ""),
            approver_name=user.get("name", ""),
        )
    elif decision == "reject":
        return RejectApproval(
            thread_ref=thread_ref,
            gate_type=gate_type,
            rejector_id=user.get("id", ""),
            reason=action.get("value", ""),
        )
    return None
