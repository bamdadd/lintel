"""Tests for InMemoryBackgroundSessionStore."""

from __future__ import annotations

from lintel.background_agents_api.store import (
    InMemoryBackgroundSessionStore,
    SessionStatus,
)


async def test_create_session() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="coder", task_description="implement feature X")
    assert session.session_id
    assert session.agent_role == "coder"
    assert session.task == "implement feature X"
    assert session.status == SessionStatus.PENDING


async def test_get_session() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="reviewer", task_description="review PR")
    got = await store.get(session.session_id)
    assert got is not None
    assert got.session_id == session.session_id


async def test_get_missing_session() -> None:
    store = InMemoryBackgroundSessionStore()
    assert await store.get("nonexistent") is None


async def test_list_all() -> None:
    store = InMemoryBackgroundSessionStore()
    await store.create(agent_role="coder", task_description="task 1")
    await store.create(agent_role="reviewer", task_description="task 2")
    sessions = await store.list_all()
    assert len(sessions) == 2


async def test_mark_running() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="coder", task_description="work")
    await store.mark_running(session.session_id)
    got = await store.get(session.session_id)
    assert got is not None
    assert got.status == SessionStatus.RUNNING
    assert got.started_at is not None


async def test_mark_completed() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="coder", task_description="work")
    await store.mark_running(session.session_id)
    await store.mark_completed(session.session_id, result={"output": "done"})
    got = await store.get(session.session_id)
    assert got is not None
    assert got.status == SessionStatus.COMPLETED
    assert got.result == {"output": "done"}
    assert got.finished_at is not None


async def test_mark_failed() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="coder", task_description="work")
    await store.mark_failed(session.session_id, error="boom")
    got = await store.get(session.session_id)
    assert got is not None
    assert got.status == SessionStatus.FAILED
    assert got.error == "boom"


async def test_mark_cancelled() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="coder", task_description="work")
    await store.mark_cancelled(session.session_id)
    got = await store.get(session.session_id)
    assert got is not None
    assert got.status == SessionStatus.CANCELLED


async def test_append_log() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="coder", task_description="work")
    await store.append_log(session.session_id, "info", "hello")
    await store.append_log(session.session_id, "error", "oops")
    got = await store.get(session.session_id)
    assert got is not None
    assert len(got.logs) == 2
    assert got.logs[0].message == "hello"
    assert got.logs[1].level == "error"


async def test_delete() -> None:
    store = InMemoryBackgroundSessionStore()
    session = await store.create(agent_role="coder", task_description="work")
    await store.delete(session.session_id)
    assert await store.get(session.session_id) is None


async def test_delete_nonexistent_is_noop() -> None:
    store = InMemoryBackgroundSessionStore()
    await store.delete("nonexistent")  # should not raise
