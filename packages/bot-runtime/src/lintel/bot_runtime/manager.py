"""BotLifecycleManager — manages runtime state of all registered bot instances."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Protocol

import structlog

from lintel.bot_runtime.types import BotConnectionState, BotHealth, _ManagedBot
from lintel.domain.types import BotPlatform, BotStatus

if TYPE_CHECKING:
    from lintel.bots_api.store import InMemoryBotStore
    from lintel.channels.registry import ChannelRegistry
    from lintel.domain.types import Bot

logger = structlog.get_logger()

# Exponential backoff constants
_INITIAL_BACKOFF_S = 1.0
_MAX_BACKOFF_S = 60.0
_BACKOFF_MULTIPLIER = 2.0


class AdapterFactory(Protocol):
    """Creates a channel adapter for a given bot and registers it."""

    async def create_adapter(self, bot: Bot) -> Any:  # noqa: ANN401
        """Create and return a channel adapter for the bot.

        Returns the adapter or None if the platform is unsupported.
        """
        ...

    async def destroy_adapter(self, bot_id: str, platform: str) -> None:
        """Tear down a previously created adapter."""
        ...


class BotLifecycleManager:
    """Manages the runtime lifecycle of all registered bot instances.

    Responsibilities:
    - On startup, loads all enabled bots and starts their connections
    - Reacts to bot CRUD events to hot-reload connections
    - Reconnects failed bots with exponential backoff
    - Exposes per-bot health status
    """

    def __init__(
        self,
        bot_store: InMemoryBotStore,
        channel_registry: ChannelRegistry,
        adapter_factory: AdapterFactory,
    ) -> None:
        self._bot_store = bot_store
        self._channel_registry = channel_registry
        self._adapter_factory = adapter_factory
        self._managed: dict[str, _ManagedBot] = {}
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------

    async def start_all(self) -> int:
        """Load all enabled bots from the store and start their connections.

        Returns the number of bots started.
        """
        bots = await self._bot_store.list_all()
        started = 0
        for bot in bots:
            if bot.status != BotStatus.ACTIVE:
                continue
            await self.start_bot(bot.bot_id)
            started += 1
        logger.info("bot_lifecycle.start_all", started=started, total=len(bots))
        return started

    async def stop_all(self) -> None:
        """Stop all managed bot connections."""
        bot_ids = list(self._managed.keys())
        for bot_id in bot_ids:
            await self.stop_bot(bot_id)
        logger.info("bot_lifecycle.stop_all", stopped=len(bot_ids))

    # ------------------------------------------------------------------
    # Per-bot lifecycle
    # ------------------------------------------------------------------

    async def start_bot(self, bot_id: str) -> bool:
        """Start a bot connection. Returns True if started successfully."""
        bot = await self._bot_store.get(bot_id)
        if bot is None:
            logger.warning("bot_lifecycle.start.not_found", bot_id=bot_id)
            return False

        async with self._lock:
            # Stop existing connection if running
            if bot_id in self._managed:
                await self._stop_bot_unlocked(bot_id)

            managed = _ManagedBot(bot_id=bot_id, platform=bot.platform.value)
            managed.health.state = BotConnectionState.STARTING
            self._managed[bot_id] = managed

        try:
            adapter = await self._adapter_factory.create_adapter(bot)
            if adapter is None:
                logger.warning(
                    "bot_lifecycle.start.unsupported_platform",
                    bot_id=bot_id,
                    platform=bot.platform.value,
                )
                async with self._lock:
                    managed.health.mark_failed(f"unsupported platform: {bot.platform.value}")
                return False

            # Register with channel registry
            connection_id = f"bot:{bot_id}"
            channel_type = _platform_to_channel_type(bot.platform)
            if channel_type is not None:
                self._channel_registry.register(connection_id, channel_type, adapter)

            async with self._lock:
                managed.health.mark_connected()
                managed.cancel = adapter  # keep adapter ref for teardown

            logger.info(
                "bot_lifecycle.started",
                bot_id=bot_id,
                platform=bot.platform.value,
            )
            return True

        except Exception as exc:
            logger.error(
                "bot_lifecycle.start.failed",
                bot_id=bot_id,
                error=str(exc),
            )
            async with self._lock:
                managed.health.mark_failed(str(exc))
            # Schedule reconnect
            self._schedule_reconnect(bot_id)
            return False

    async def stop_bot(self, bot_id: str) -> bool:
        """Stop a bot connection. Returns True if the bot was running."""
        async with self._lock:
            return await self._stop_bot_unlocked(bot_id)

    async def _stop_bot_unlocked(self, bot_id: str) -> bool:
        """Stop without acquiring lock (caller must hold self._lock)."""
        managed = self._managed.pop(bot_id, None)
        if managed is None:
            return False

        # Unregister from channel registry
        connection_id = f"bot:{bot_id}"
        self._channel_registry.unregister(connection_id)

        # Tear down the adapter
        try:
            await self._adapter_factory.destroy_adapter(bot_id, managed.platform)
        except Exception as exc:
            logger.warning("bot_lifecycle.stop.cleanup_error", bot_id=bot_id, error=str(exc))

        managed.health.state = BotConnectionState.STOPPED
        logger.info("bot_lifecycle.stopped", bot_id=bot_id)
        return True

    async def restart_bot(self, bot_id: str) -> bool:
        """Restart a bot connection (stop then start)."""
        await self.stop_bot(bot_id)
        return await self.start_bot(bot_id)

    # ------------------------------------------------------------------
    # Event handlers (called from event bus subscriptions)
    # ------------------------------------------------------------------

    async def handle_bot_created(self, event: Any) -> None:  # noqa: ANN401
        """Handle BotCreated event — start the new bot."""
        bot_id = (event.payload or {}).get("resource_id", "")
        if bot_id:
            await self.start_bot(bot_id)

    async def handle_bot_updated(self, event: Any) -> None:  # noqa: ANN401
        """Handle BotUpdated event — restart the bot to pick up changes."""
        bot_id = (event.payload or {}).get("resource_id", "")
        if not bot_id:
            return

        bot = await self._bot_store.get(bot_id)
        if bot is None:
            await self.stop_bot(bot_id)
            return

        if bot.status != BotStatus.ACTIVE:
            await self.stop_bot(bot_id)
        elif bot_id in self._managed:
            await self.restart_bot(bot_id)
        else:
            await self.start_bot(bot_id)

    async def handle_bot_removed(self, event: Any) -> None:  # noqa: ANN401
        """Handle BotRemoved event — stop and remove the bot."""
        bot_id = (event.payload or {}).get("resource_id", "")
        if bot_id:
            await self.stop_bot(bot_id)

    # ------------------------------------------------------------------
    # Reconnect with exponential backoff
    # ------------------------------------------------------------------

    def _schedule_reconnect(self, bot_id: str) -> None:
        """Schedule an async reconnection attempt with backoff."""
        managed = self._managed.get(bot_id)
        if managed is None:
            return

        attempts = managed.health.reconnect_attempts
        delay = min(_INITIAL_BACKOFF_S * (_BACKOFF_MULTIPLIER**attempts), _MAX_BACKOFF_S)

        async def _reconnect() -> None:
            await asyncio.sleep(delay)
            managed_now = self._managed.get(bot_id)
            if managed_now is None:
                return  # bot was removed while waiting
            managed_now.health.mark_reconnecting()
            logger.info(
                "bot_lifecycle.reconnecting",
                bot_id=bot_id,
                attempt=managed_now.health.reconnect_attempts,
                delay_s=delay,
            )
            await self.start_bot(bot_id)

        task = asyncio.create_task(_reconnect())
        # Store task reference so it's not garbage-collected
        managed._reconnect_task = task  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Health / status
    # ------------------------------------------------------------------

    def get_health(self, bot_id: str) -> BotHealth | None:
        """Get health for a single bot. Returns None if not managed."""
        managed = self._managed.get(bot_id)
        return managed.health if managed else None

    def get_all_health(self) -> list[BotHealth]:
        """Get health snapshots for all managed bots."""
        return [m.health for m in self._managed.values()]

    def is_running(self, bot_id: str) -> bool:
        """Check if a bot is currently running (connected or reconnecting)."""
        managed = self._managed.get(bot_id)
        if managed is None:
            return False
        return managed.health.state in (
            BotConnectionState.CONNECTED,
            BotConnectionState.RECONNECTING,
            BotConnectionState.STARTING,
        )


def _platform_to_channel_type(platform: BotPlatform) -> Any | None:  # noqa: ANN401
    """Convert BotPlatform to ChannelType for registry."""
    from lintel.contracts.channel_type import ChannelType

    mapping = {
        BotPlatform.SLACK: ChannelType.SLACK,
        BotPlatform.TELEGRAM: ChannelType.TELEGRAM,
    }
    return mapping.get(platform)
