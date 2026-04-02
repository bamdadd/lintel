"""Handle Slack app_mention events to trigger workflow invocations."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from slack_sdk.web.async_client import AsyncWebClient

logger = structlog.get_logger()

_URL_PATTERN = re.compile(r"<(https?://[^|>]+)(?:\|[^>]*)?>")
_MENTION_PATTERN = re.compile(r"<@[A-Z0-9]+>")


def strip_mention(text: str) -> str:
    """Remove @mention tags from message text and strip whitespace."""
    return _MENTION_PATTERN.sub("", text).strip()


def extract_urls(text: str) -> list[str]:
    """Extract URLs from Slack message text (handles <url|label> format)."""
    return _URL_PATTERN.findall(text)


async def fetch_thread_context(
    client: AsyncWebClient,
    channel: str,
    thread_ts: str,
) -> list[dict[str, Any]]:
    """Fetch all messages in a Slack thread.

    Returns a list of dicts with keys: user, text, ts.
    """
    try:
        result = await client.conversations_replies(
            channel=channel,
            ts=thread_ts,
            limit=100,
        )
        messages: list[dict[str, Any]] = []
        raw_messages: list[Any] = result.get("messages", [])
        for msg in raw_messages:
            messages.append(
                {
                    "user": msg.get("user", ""),
                    "text": msg.get("text", ""),
                    "ts": msg.get("ts", ""),
                }
            )
        return messages
    except Exception:
        logger.exception("Failed to fetch thread context", channel=channel, thread_ts=thread_ts)
        return []


def collect_thread_urls(messages: list[dict[str, Any]]) -> list[str]:
    """Collect all URLs found across thread messages."""
    urls: list[str] = []
    for msg in messages:
        text = msg.get("text", "")
        if isinstance(text, str):
            urls.extend(extract_urls(text))
    return urls
