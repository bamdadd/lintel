"""Tests for in-memory bot store."""

import pytest

from lintel.bots_api.store import InMemoryBotStore
from lintel.domain.types import Bot, BotPlatform, BotStatus


@pytest.fixture()
def store() -> InMemoryBotStore:
    return InMemoryBotStore()


async def test_add_and_get(store: InMemoryBotStore) -> None:
    bot = Bot(bot_id="b-1", name="TestBot", platform=BotPlatform.SLACK)
    await store.add(bot)
    result = await store.get("b-1")
    assert result is not None
    assert result.name == "TestBot"


async def test_get_missing_returns_none(store: InMemoryBotStore) -> None:
    assert await store.get("missing") is None


async def test_list_all(store: InMemoryBotStore) -> None:
    await store.add(Bot(bot_id="b-1", name="Bot1"))
    await store.add(Bot(bot_id="b-2", name="Bot2"))
    bots = await store.list_all()
    assert len(bots) == 2


async def test_update(store: InMemoryBotStore) -> None:
    await store.add(Bot(bot_id="b-1", name="Bot1"))
    updated = Bot(bot_id="b-1", name="Updated", status=BotStatus.INACTIVE)
    await store.update(updated)
    result = await store.get("b-1")
    assert result is not None
    assert result.name == "Updated"
    assert result.status == BotStatus.INACTIVE


async def test_remove(store: InMemoryBotStore) -> None:
    await store.add(Bot(bot_id="b-1", name="Bot1"))
    await store.remove("b-1")
    assert await store.get("b-1") is None
