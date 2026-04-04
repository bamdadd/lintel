"""Tests for BotLifecycleManager."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from lintel.bot_runtime.manager import BotLifecycleManager
from lintel.bot_runtime.types import BotConnectionState
from lintel.bots_api.store import InMemoryBotStore
from lintel.channels.registry import ChannelRegistry
from lintel.domain.types import Bot, BotPlatform, BotStatus

# ---------------------------------------------------------------------------
# Fake adapter factory for testing
# ---------------------------------------------------------------------------


@dataclass
class FakeAdapter:
    bot_id: str


class FakeAdapterFactory:
    """Test double for AdapterFactory."""

    def __init__(self, *, fail_for: set[str] | None = None) -> None:
        self.created: list[str] = []
        self.destroyed: list[str] = []
        self._fail_for = fail_for or set()

    async def create_adapter(self, bot: Bot) -> FakeAdapter | None:
        if bot.bot_id in self._fail_for:
            msg = f"simulated failure for {bot.bot_id}"
            raise RuntimeError(msg)
        if bot.platform == BotPlatform.CUSTOM:
            return None  # unsupported
        self.created.append(bot.bot_id)
        return FakeAdapter(bot_id=bot.bot_id)

    async def destroy_adapter(self, bot_id: str, platform: str) -> None:
        self.destroyed.append(bot_id)


@dataclass(frozen=True)
class _FakeEvent:
    payload: dict[str, object]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bot_store() -> InMemoryBotStore:
    return InMemoryBotStore()


@pytest.fixture
def channel_registry() -> ChannelRegistry:
    return ChannelRegistry()


@pytest.fixture
def adapter_factory() -> FakeAdapterFactory:
    return FakeAdapterFactory()


@pytest.fixture
def manager(
    bot_store: InMemoryBotStore,
    channel_registry: ChannelRegistry,
    adapter_factory: FakeAdapterFactory,
) -> BotLifecycleManager:
    return BotLifecycleManager(bot_store, channel_registry, adapter_factory)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_start_all_starts_active_bots(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await bot_store.add(
        Bot(bot_id="b2", name="Bot 2", platform=BotPlatform.TELEGRAM, status=BotStatus.INACTIVE)
    )
    await bot_store.add(Bot(bot_id="b3", name="Bot 3", platform=BotPlatform.TELEGRAM))

    started = await manager.start_all()
    assert started == 2
    assert "b1" in adapter_factory.created
    assert "b2" not in adapter_factory.created
    assert "b3" in adapter_factory.created


async def test_start_bot_registers_in_channel_registry(
    bot_store: InMemoryBotStore,
    channel_registry: ChannelRegistry,
    manager: BotLifecycleManager,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    result = await manager.start_bot("b1")
    assert result is True
    assert channel_registry.is_connection_registered("bot:b1")


async def test_start_bot_not_found(manager: BotLifecycleManager) -> None:
    result = await manager.start_bot("missing")
    assert result is False


async def test_start_bot_unsupported_platform(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Custom Bot", platform=BotPlatform.CUSTOM))
    result = await manager.start_bot("b1")
    assert result is False
    health = manager.get_health("b1")
    assert health is not None
    assert health.state == BotConnectionState.FAILED


async def test_stop_bot(
    bot_store: InMemoryBotStore,
    channel_registry: ChannelRegistry,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await manager.start_bot("b1")
    assert manager.is_running("b1")

    result = await manager.stop_bot("b1")
    assert result is True
    assert not manager.is_running("b1")
    assert "b1" in adapter_factory.destroyed
    assert not channel_registry.is_connection_registered("bot:b1")


async def test_stop_bot_not_running(manager: BotLifecycleManager) -> None:
    result = await manager.stop_bot("missing")
    assert result is False


async def test_restart_bot(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await manager.start_bot("b1")
    result = await manager.restart_bot("b1")
    assert result is True
    assert "b1" in adapter_factory.destroyed
    assert adapter_factory.created.count("b1") == 2


async def test_get_all_health(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await bot_store.add(Bot(bot_id="b2", name="Bot 2", platform=BotPlatform.TELEGRAM))
    await manager.start_bot("b1")
    await manager.start_bot("b2")
    health_list = manager.get_all_health()
    assert len(health_list) == 2
    assert {h.bot_id for h in health_list} == {"b1", "b2"}


async def test_stop_all(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await bot_store.add(Bot(bot_id="b2", name="Bot 2", platform=BotPlatform.TELEGRAM))
    await manager.start_all()
    await manager.stop_all()
    assert len(manager.get_all_health()) == 0
    assert len(adapter_factory.destroyed) == 2


async def test_handle_bot_created(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await manager.handle_bot_created(_FakeEvent(payload={"resource_id": "b1", "name": "Bot 1"}))
    assert "b1" in adapter_factory.created


async def test_handle_bot_updated_restarts(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await manager.start_bot("b1")
    await manager.handle_bot_updated(_FakeEvent(payload={"resource_id": "b1", "fields": ["name"]}))
    # Should have been destroyed and recreated
    assert "b1" in adapter_factory.destroyed
    assert adapter_factory.created.count("b1") == 2


async def test_handle_bot_updated_stops_inactive(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    bot = Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK)
    await bot_store.add(bot)
    await manager.start_bot("b1")

    # Update bot to inactive
    inactive = Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK, status=BotStatus.INACTIVE)
    await bot_store.update(inactive)
    await manager.handle_bot_updated(
        _FakeEvent(payload={"resource_id": "b1", "fields": ["status"]})
    )
    assert not manager.is_running("b1")


async def test_handle_bot_removed(
    bot_store: InMemoryBotStore,
    manager: BotLifecycleManager,
    adapter_factory: FakeAdapterFactory,
) -> None:
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))
    await manager.start_bot("b1")
    await manager.handle_bot_removed(_FakeEvent(payload={"resource_id": "b1", "name": "Bot 1"}))
    assert not manager.is_running("b1")
    assert "b1" in adapter_factory.destroyed


async def test_start_bot_failure_marks_failed(
    bot_store: InMemoryBotStore,
    channel_registry: ChannelRegistry,
) -> None:
    factory = FakeAdapterFactory(fail_for={"b1"})
    mgr = BotLifecycleManager(bot_store, channel_registry, factory)
    await bot_store.add(Bot(bot_id="b1", name="Bot 1", platform=BotPlatform.SLACK))

    result = await mgr.start_bot("b1")
    assert result is False
    health = mgr.get_health("b1")
    assert health is not None
    assert health.state == BotConnectionState.FAILED
    assert "simulated failure" in health.error
