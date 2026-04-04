"""Tests for in-memory workspace store."""

from __future__ import annotations

from lintel.multi_tenancy_api.store import InMemoryWorkspaceStore, Workspace


async def test_add_and_get() -> None:
    store = InMemoryWorkspaceStore()
    ws = Workspace(workspace_id="ws-1", name="Acme", slug="acme", owner_user_id="u1")
    await store.add(ws)
    result = await store.get("ws-1")
    assert result is not None
    assert result.name == "Acme"


async def test_get_not_found() -> None:
    store = InMemoryWorkspaceStore()
    assert await store.get("nope") is None


async def test_get_by_slug() -> None:
    store = InMemoryWorkspaceStore()
    ws = Workspace(workspace_id="ws-1", name="Acme", slug="acme", owner_user_id="u1")
    await store.add(ws)
    result = await store.get_by_slug("acme")
    assert result is not None
    assert result.workspace_id == "ws-1"


async def test_get_by_slug_not_found() -> None:
    store = InMemoryWorkspaceStore()
    assert await store.get_by_slug("nope") is None


async def test_list_all() -> None:
    store = InMemoryWorkspaceStore()
    await store.add(Workspace(workspace_id="1", name="A", slug="a", owner_user_id="u1"))
    await store.add(Workspace(workspace_id="2", name="B", slug="b", owner_user_id="u2"))
    result = await store.list_all()
    assert len(result) == 2


async def test_list_by_owner() -> None:
    store = InMemoryWorkspaceStore()
    await store.add(Workspace(workspace_id="1", name="A", slug="a", owner_user_id="u1"))
    await store.add(Workspace(workspace_id="2", name="B", slug="b", owner_user_id="u2"))
    await store.add(Workspace(workspace_id="3", name="C", slug="c", owner_user_id="u1"))
    result = await store.list_by_owner("u1")
    assert len(result) == 2
    assert all(w.owner_user_id == "u1" for w in result)
