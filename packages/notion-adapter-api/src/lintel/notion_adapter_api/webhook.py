"""Notion webhook event parsing and signature verification."""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def verify_signature(body: bytes, signature: str, secret: str) -> bool:
    """Verify the HMAC-SHA256 signature of a Notion webhook payload.

    Args:
        body: Raw request body bytes.
        signature: The ``X-Notion-Signature`` header value (hex digest).
        secret: The webhook signing secret configured in Notion.

    Returns:
        ``True`` when the signature is valid.
    """
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def parse_webhook_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Parse a Notion webhook payload into a normalised event dict.

    Returns a dict with ``event_type``, ``page_id``, ``database_id``, and raw ``data``.
    """
    event_type = payload.get("type", "unknown")
    data = payload.get("data", {})
    page_id = data.get("id", "")

    # Extract parent database_id when available
    parent = data.get("parent", {})
    database_id = parent.get("database_id", "")

    return {
        "event_type": event_type,
        "page_id": page_id,
        "database_id": database_id,
        "data": data,
    }
