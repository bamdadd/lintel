"""Telegram inline keyboards for approval requests."""

from __future__ import annotations

from typing import Any


def build_approval_keyboard(approval_request_id: str) -> dict[str, Any]:
    """Build an InlineKeyboardMarkup dict for an approval request.

    Callback data is kept under Telegram's 64-byte limit using short
    prefixes: 'a:{id}' for approve, 'r:{id}' for reject.
    The approval_request_id is truncated to 58 chars max to stay safe.
    """
    safe_id = approval_request_id[:58]
    return {
        "inline_keyboard": [
            [
                {
                    "text": "✅ Approve",
                    "callback_data": f"a:{safe_id}",
                },
                {
                    "text": "❌ Reject",
                    "callback_data": f"r:{safe_id}",
                },
            ],
        ],
    }


def parse_callback_data(data: str) -> tuple[str, str]:
    """Parse callback_data into (action, approval_request_id).

    Returns:
        Tuple of (action, approval_request_id) where action is
        'approve' or 'reject'.

    Raises:
        ValueError: If the callback data format is invalid.
    """
    if not data or ":" not in data:
        msg = f"Invalid callback data format: {data!r}"
        raise ValueError(msg)

    prefix, request_id = data.split(":", 1)
    if prefix == "a":
        return ("approve", request_id)
    if prefix == "r":
        return ("reject", request_id)
    msg = f"Unknown callback prefix: {prefix!r}"
    raise ValueError(msg)
