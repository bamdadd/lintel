"""Integration tests for PostgresChatStore."""

from __future__ import annotations

from typing import TYPE_CHECKING

import asyncpg
import pytest
from lintel.infrastructure.persistence.stores import PostgresChatStore

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


@pytest.fixture
async def chat_store(postgres_url: str) -> AsyncGenerator[PostgresChatStore]:
    pool = await asyncpg.create_pool(postgres_url)
    assert pool is not None
    async with pool.acquire() as conn:
        with open("migrations/003_create_entities.sql") as f:
            await conn.execute(f.read())
        await conn.execute("DELETE FROM entities WHERE kind = 'conversation'")
    store = PostgresChatStore(pool)
    yield store
    await pool.close()


async def test_create_and_get_conversation(chat_store: PostgresChatStore) -> None:
    conv = await chat_store.create(
        conversation_id="c1",
        user_id="u1",
        display_name="Alice",
        project_id="p1",
        model_id="gpt-4",
    )
    assert conv["conversation_id"] == "c1"
    assert conv["user_id"] == "u1"
    assert conv["messages"] == []

    fetched = await chat_store.get("c1")
    assert fetched is not None
    assert fetched["conversation_id"] == "c1"
    assert fetched["model_id"] == "gpt-4"


async def test_get_missing_returns_none(chat_store: PostgresChatStore) -> None:
    assert await chat_store.get("nonexistent") is None


async def test_add_messages_and_ordering(chat_store: PostgresChatStore) -> None:
    await chat_store.create(
        conversation_id="c2",
        user_id="u1",
        display_name="Alice",
        project_id="p1",
    )

    await chat_store.add_message(
        "c2", user_id="u1", display_name="Alice", role="user", content="Hello"
    )
    await chat_store.add_message(
        "c2", user_id="bot", display_name="Bot", role="agent", content="Hi there"
    )
    await chat_store.add_message(
        "c2", user_id="u1", display_name="Alice", role="user", content="How are you?"
    )

    conv = await chat_store.get("c2")
    assert conv is not None
    messages = conv["messages"]
    assert len(messages) == 3
    assert messages[0]["content"] == "Hello"
    assert messages[1]["content"] == "Hi there"
    assert messages[2]["content"] == "How are you?"

    # Each message has a unique ID
    ids = {m["message_id"] for m in messages}
    assert len(ids) == 3


async def test_add_message_to_missing_conversation(chat_store: PostgresChatStore) -> None:
    with pytest.raises(KeyError, match="not found"):
        await chat_store.add_message(
            "missing", user_id="u1", display_name="A", role="user", content="x"
        )


async def test_message_persistence_across_reads(chat_store: PostgresChatStore) -> None:
    """Messages survive re-reads (simulates server restart)."""
    await chat_store.create(conversation_id="c3", user_id="u1", display_name="A", project_id="p1")
    await chat_store.add_message(
        "c3", user_id="u1", display_name="A", role="user", content="persisted"
    )

    # Re-read from DB
    conv = await chat_store.get("c3")
    assert conv is not None
    assert len(conv["messages"]) == 1
    assert conv["messages"][0]["content"] == "persisted"


async def test_list_all_with_filters(chat_store: PostgresChatStore) -> None:
    await chat_store.create(conversation_id="c4", user_id="u1", display_name="A", project_id="p1")
    await chat_store.create(conversation_id="c5", user_id="u2", display_name="B", project_id="p1")
    await chat_store.create(conversation_id="c6", user_id="u1", display_name="A", project_id="p2")

    all_convs = await chat_store.list_all()
    assert len(all_convs) == 3

    u1_convs = await chat_store.list_all(user_id="u1")
    assert len(u1_convs) == 2

    p1_convs = await chat_store.list_all(project_id="p1")
    assert len(p1_convs) == 2

    u1_p1 = await chat_store.list_all(user_id="u1", project_id="p1")
    assert len(u1_p1) == 1
    assert u1_p1[0]["conversation_id"] == "c4"


async def test_delete_conversation(chat_store: PostgresChatStore) -> None:
    await chat_store.create(conversation_id="c7", user_id="u1", display_name="A", project_id="p1")
    await chat_store.add_message("c7", user_id="u1", display_name="A", role="user", content="bye")

    result = await chat_store.delete("c7")
    assert result is True

    assert await chat_store.get("c7") is None
    assert await chat_store.delete("c7") is False


async def test_update_fields(chat_store: PostgresChatStore) -> None:
    await chat_store.create(conversation_id="c8", user_id="u1", display_name="A", project_id="p1")
    await chat_store.update_fields("c8", model_id="claude-3", title="My Chat")

    conv = await chat_store.get("c8")
    assert conv is not None
    assert conv["model_id"] == "claude-3"
    assert conv["title"] == "My Chat"
