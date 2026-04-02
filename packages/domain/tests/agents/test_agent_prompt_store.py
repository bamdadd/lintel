"""Tests for InMemoryAgentPromptStore."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.agents.stores import InMemoryAgentPromptStore
from lintel.domain.agents.types import AgentPromptVersion


async def _make_prompt(
    agent_id: str = "agent-1", version: int = 1, text: str = "You are helpful."
) -> AgentPromptVersion:
    return AgentPromptVersion(
        agent_id=agent_id,
        version=version,
        prompt_text=text,
        author="alice",
        created_at=datetime.now(UTC),
    )


async def test_save_and_get_latest() -> None:
    store = InMemoryAgentPromptStore()
    p1 = await _make_prompt(version=1)
    p2 = await _make_prompt(version=2, text="v2")
    await store.save_version(p1)
    await store.save_version(p2)
    latest = await store.get_latest("agent-1")
    assert latest is not None
    assert latest.version == 2
    assert latest.prompt_text == "v2"


async def test_get_latest_returns_none_for_unknown() -> None:
    store = InMemoryAgentPromptStore()
    assert await store.get_latest("unknown") is None


async def test_get_version() -> None:
    store = InMemoryAgentPromptStore()
    p1 = await _make_prompt(version=1, text="v1")
    p2 = await _make_prompt(version=2, text="v2")
    await store.save_version(p1)
    await store.save_version(p2)
    result = await store.get_version("agent-1", 1)
    assert result is not None
    assert result.prompt_text == "v1"


async def test_get_version_returns_none() -> None:
    store = InMemoryAgentPromptStore()
    assert await store.get_version("agent-1", 99) is None


async def test_list_versions_ordered_newest_first() -> None:
    store = InMemoryAgentPromptStore()
    for v in range(1, 4):
        await store.save_version(await _make_prompt(version=v, text=f"v{v}"))
    versions = await store.list_versions("agent-1")
    assert len(versions) == 3
    assert [v.version for v in versions] == [3, 2, 1]


async def test_list_versions_empty() -> None:
    store = InMemoryAgentPromptStore()
    assert await store.list_versions("agent-1") == []


async def test_multiple_agents_isolated() -> None:
    store = InMemoryAgentPromptStore()
    await store.save_version(await _make_prompt(agent_id="a", version=1))
    await store.save_version(await _make_prompt(agent_id="b", version=1))
    assert len(await store.list_versions("a")) == 1
    assert len(await store.list_versions("b")) == 1


async def test_prompt_version_is_frozen() -> None:
    p = await _make_prompt()
    try:
        p.version = 99  # type: ignore[misc]
        raise AssertionError("Should not allow mutation")
    except AttributeError:
        pass
