"""Telegram long-polling loop for local development (no public webhook needed)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from lintel.telegram.adapter import TelegramChannelAdapter

logger = structlog.get_logger()


async def run_polling(
    adapter: TelegramChannelAdapter,
    dispatch_update: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    *,
    poll_timeout: int = 30,
) -> None:
    """Run a long-polling loop that fetches updates and dispatches them.

    Args:
        adapter: TelegramChannelAdapter with a valid bot token.
        dispatch_update: Async callable(update_dict) that processes each update
            the same way the webhook handler would.
        poll_timeout: Telegram long-poll timeout in seconds.
    """
    # Delete any existing webhook so getUpdates works
    await adapter.delete_webhook()
    logger.info("telegram.polling.started", bot_username=adapter.bot_username)

    offset: int | None = None
    while True:
        try:
            updates = await adapter.get_updates(offset=offset, timeout=poll_timeout)
            for update in updates:
                update_id = update.get("update_id")
                if update_id is not None:
                    offset = update_id + 1
                try:
                    await dispatch_update(update)
                except Exception:
                    logger.exception("telegram.polling.dispatch_error", update_id=update_id)
        except asyncio.CancelledError:
            logger.info("telegram.polling.stopped")
            raise
        except Exception:
            logger.exception("telegram.polling.error")
            await asyncio.sleep(5)
