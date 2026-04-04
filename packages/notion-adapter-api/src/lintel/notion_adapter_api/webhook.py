"""Notion webhook event parsing utilities."""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def parse_webhook_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse a Notion webhook payload into a normalised event dict.

    Returns a dict with ``event_type``, ``page_id`` (if applicable), and raw ``data``.
    """
    event_type = payload.get("type", "unknown")
    data = payload.get("data", {})
    page_id = data.get("id", "")

    return {
        "event_type": event_type,
        "page_id": page_id,
        "data": data,
    }
