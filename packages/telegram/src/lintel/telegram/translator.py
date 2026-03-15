"""Translate Telegram Update objects into InboundMessage envelopes."""

from __future__ import annotations

import re
from typing import Any

import structlog

from lintel.contracts.channel_type import ChannelType
from lintel.contracts.inbound_message import InboundMessage

logger = structlog.get_logger()

# Pattern to detect @mention of the bot in group messages
BOT_MENTION_PATTERN = re.compile(r"@(\w+)")


def translate_message_update(
    update: dict[str, Any],
    bot_username: str = "",
) -> InboundMessage | None:
    """Translate a Telegram Update dict into an InboundMessage envelope.

    Args:
        update: Raw Telegram Update as a dict.
        bot_username: The bot's username (without @) for @mention filtering
            in group chats. If empty, all group messages are processed.

    Returns:
        InboundMessage if the update should be processed, None otherwise.
    """
    message = update.get("message")
    if message is None:
        return None

    chat = message.get("chat", {})
    chat_id = str(chat.get("id", ""))
    chat_type = chat.get("type", "private")
    text = message.get("text", "")
    from_user = message.get("from", {})
    sender_id = str(from_user.get("id", ""))
    message_id = str(message.get("message_id", ""))

    if not chat_id or not text:
        return None

    # For group/supergroup chats, only process if bot is @mentioned
    if chat_type in ("group", "supergroup") and bot_username:
        mentions = BOT_MENTION_PATTERN.findall(text)
        if not any(m.lower() == bot_username.lower() for m in mentions):
            return None
        # Strip the @mention from the text
        text = re.sub(rf"@{re.escape(bot_username)}\s*", "", text, flags=re.IGNORECASE).strip()

    # Forum topic support: use message_thread_id if present
    message_thread_id = message.get("message_thread_id")
    if message_thread_id is not None:
        thread_id = str(message_thread_id)
    elif chat_type == "private":
        # Private chats: use chat_id as thread_id for stable conversation ID
        thread_id = chat_id
    else:
        # Non-threaded group messages: use message_id
        thread_id = message_id

    return InboundMessage(
        channel_type=ChannelType.TELEGRAM,
        channel_id=chat_id,
        thread_id=thread_id,
        sender_id=sender_id,
        text=text,
        raw_payload=update,
        workspace_id="telegram",
    )


def translate_callback_query(
    update: dict[str, Any],
) -> tuple[str, dict[str, Any]] | None:
    """Extract callback query data from an Update for approval handling.

    Returns:
        Tuple of (callback_data, full_callback_query_dict) or None if
        the update doesn't contain a callback query.
    """
    callback_query = update.get("callback_query")
    if callback_query is None:
        return None

    data = callback_query.get("data", "")
    if not data:
        return None

    return (data, callback_query)
