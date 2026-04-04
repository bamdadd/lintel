"""Default adapter factory for BotLifecycleManager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from lintel.domain.types import BotPlatform

if TYPE_CHECKING:
    from lintel.domain.types import Bot

logger = structlog.get_logger()


class DefaultAdapterFactory:
    """Creates channel adapters from Bot entities.

    Currently supports Telegram (via bot_token in credential store)
    and Slack (placeholder — Slack bots are managed separately via OAuth).
    """

    def __init__(self, credential_store: Any = None) -> None:  # noqa: ANN401
        self._credential_store = credential_store
        self._adapters: dict[str, Any] = {}

    async def create_adapter(self, bot: Bot) -> Any | None:  # noqa: ANN401
        """Create an adapter for the given bot.

        Returns the adapter instance, or None if the platform is unsupported.
        """
        if bot.platform == BotPlatform.TELEGRAM:
            return await self._create_telegram_adapter(bot)
        if bot.platform == BotPlatform.SLACK:
            return await self._create_slack_adapter(bot)
        return None

    async def destroy_adapter(self, bot_id: str, platform: str) -> None:
        """Tear down a previously created adapter."""
        adapter = self._adapters.pop(bot_id, None)
        if adapter is None:
            return
        # Telegram adapters don't need explicit cleanup (httpx sessions are per-request)
        logger.info("bot_adapter.destroyed", bot_id=bot_id, platform=platform)

    async def _create_telegram_adapter(self, bot: Bot) -> Any | None:  # noqa: ANN401
        """Create a Telegram adapter from stored credentials."""
        bot_token = await self._resolve_bot_token(bot)
        if not bot_token:
            logger.warning("bot_adapter.telegram.no_token", bot_id=bot.bot_id)
            return None

        from lintel.telegram.adapter import TelegramChannelAdapter

        adapter = TelegramChannelAdapter(bot_token=bot_token)
        # Verify the token
        try:
            await adapter.get_me()
        except Exception as exc:
            logger.error(
                "bot_adapter.telegram.invalid_token",
                bot_id=bot.bot_id,
                error=str(exc),
            )
            msg = f"invalid telegram token: {exc}"
            raise RuntimeError(msg) from exc

        self._adapters[bot.bot_id] = adapter
        logger.info(
            "bot_adapter.telegram.created",
            bot_id=bot.bot_id,
            bot_username=adapter.bot_username,
        )
        return adapter

    async def _create_slack_adapter(self, bot: Bot) -> Any | None:  # noqa: ANN401
        """Create a Slack adapter stub.

        Full Slack adapter creation requires OAuth and Socket Mode setup,
        which is handled by the multi-slack-bot flow. This returns a minimal
        marker so the lifecycle manager can track the bot.
        """
        # For now, Slack bots managed via multi-slack-bot-api have their own lifecycle.
        # Return None to indicate this platform is handled externally.
        logger.info(
            "bot_adapter.slack.deferred",
            bot_id=bot.bot_id,
            message="Slack bots use OAuth-based lifecycle (multi-slack-bot-api)",
        )
        return None

    async def _resolve_bot_token(self, bot: Bot) -> str:
        """Resolve a bot token from the credential store."""
        if self._credential_store is None:
            return ""

        credential_id = f"bot:{bot.bot_id}:token"
        try:
            secret = await self._credential_store.get_secret(credential_id)
            if secret:
                return str(secret)
        except Exception:
            pass

        return ""
