"""Tests for InMemoryAgentMemoryStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lintel.domain.agents.stores import InMemoryAgentMemoryStore
from lintel.domain.agents.types import AgentMemoryEntry, MemoryCategory


def _entry(
    agent_id: str = "agent-1",
    key: str = "pref",
    value: str = "dark-mode",
    category: MemoryCategory = MemoryCategory.PREFERENCE,
    expires_at: datetime | None = None,
) -> AgentMemoryEntry:
    return AgentMemoryEntry(
        agent_id=agent_id,
        key=key,
        value=value,
        category=category,
        created_at=datetime.now(UTC),
        expires_at=expires_at,
    )


async def test_save_and_get() -> None:
    store = InMemoryAgentMemoryStore()
    e = _entry()
    await store.save(e)
    got = await store.get("agent-1", "pref")
    assert got is not None
    assert got.value == "dark-mode"


async def test_get_returns_none_for_missing() -> None:
    store = InMemoryAgentMemoryStore()
    assert await store.get("agent-1", "missing") is None


async def test_save_overwrites() -> None:
    store = InMemoryAgentMemoryStore()
    await store.save(_entry(value="v1"))
    await store.save(_entry(value="v2"))
    got = await store.get("agent-1", "pref")
    assert got is not None
    assert got.value == "v2"


async def test_list_by_agent() -> None:
    store = InMemoryAgentMemoryStore()
    await store.save(_entry(key="a"))
    await store.save(_entry(key="b"))
    await store.save(_entry(agent_id="other", key="c"))
    entries = await store.list_by_agent("agent-1")
    assert len(entries) == 2


async def test_search_by_key() -> None:
    store = InMemoryAgentMemoryStore()
    await store.save(_entry(key="favorite_color", value="blue"))
    await store.save(_entry(key="name", value="alice"))
    results = await store.search("agent-1", "color")
    assert len(results) == 1
    assert results[0].key == "favorite_color"


async def test_search_by_value() -> None:
    store = InMemoryAgentMemoryStore()
    await store.save(_entry(key="k1", value="the quick brown fox"))
    results = await store.search("agent-1", "brown")
    assert len(results) == 1


async def test_search_case_insensitive() -> None:
    store = InMemoryAgentMemoryStore()
    await store.save(_entry(key="Theme", value="DARK"))
    results = await store.search("agent-1", "theme")
    assert len(results) == 1


async def test_delete_existing() -> None:
    store = InMemoryAgentMemoryStore()
    await store.save(_entry())
    assert await store.delete("agent-1", "pref") is True
    assert await store.get("agent-1", "pref") is None


async def test_delete_missing() -> None:
    store = InMemoryAgentMemoryStore()
    assert await store.delete("agent-1", "nope") is False


async def test_expired_entry_not_returned_by_get() -> None:
    store = InMemoryAgentMemoryStore()
    past = datetime.now(UTC) - timedelta(hours=1)
    await store.save(_entry(expires_at=past))
    assert await store.get("agent-1", "pref") is None


async def test_expired_entry_excluded_from_list() -> None:
    store = InMemoryAgentMemoryStore()
    past = datetime.now(UTC) - timedelta(hours=1)
    await store.save(_entry(key="expired", expires_at=past))
    await store.save(_entry(key="valid"))
    entries = await store.list_by_agent("agent-1")
    assert len(entries) == 1
    assert entries[0].key == "valid"


async def test_expired_entry_excluded_from_search() -> None:
    store = InMemoryAgentMemoryStore()
    past = datetime.now(UTC) - timedelta(hours=1)
    await store.save(_entry(key="old", value="match", expires_at=past))
    await store.save(_entry(key="new", value="match"))
    results = await store.search("agent-1", "match")
    assert len(results) == 1
    assert results[0].key == "new"


async def test_memory_category_enum() -> None:
    assert MemoryCategory.CONTEXT == "context"
    assert MemoryCategory.PREFERENCE == "preference"
    assert MemoryCategory.LEARNED == "learned"


async def test_memory_entry_is_frozen() -> None:
    e = _entry()
    try:
        e.value = "changed"  # type: ignore[misc]
        raise AssertionError("Should not allow mutation")
    except AttributeError:
        pass
