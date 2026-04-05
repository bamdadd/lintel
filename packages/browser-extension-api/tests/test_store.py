"""Tests for in-memory component modification store."""

import pytest

from lintel.browser_extension_api.store import InMemoryComponentModificationStore
from lintel.browser_extension_api.types import ComponentModification


@pytest.fixture()
def store() -> InMemoryComponentModificationStore:
    return InMemoryComponentModificationStore()


def _make_mod(**overrides: object) -> ComponentModification:
    defaults: dict[str, object] = {
        "id": "mod-1",
        "project_id": "proj-1",
        "component_path": "src/App.tsx",
        "instructions": "Change color",
    }
    defaults.update(overrides)
    return ComponentModification(**defaults)  # type: ignore[arg-type]


class TestAdd:
    async def test_returns_dict(self, store: InMemoryComponentModificationStore) -> None:
        result = await store.add(_make_mod())
        assert result["id"] == "mod-1"
        assert result["status"] == "pending"

    async def test_stores_item(self, store: InMemoryComponentModificationStore) -> None:
        await store.add(_make_mod())
        assert await store.get("mod-1") is not None


class TestGet:
    async def test_missing(self, store: InMemoryComponentModificationStore) -> None:
        assert await store.get("nope") is None


class TestListAll:
    async def test_empty(self, store: InMemoryComponentModificationStore) -> None:
        assert await store.list_all() == []

    async def test_returns_all(self, store: InMemoryComponentModificationStore) -> None:
        await store.add(_make_mod(id="a"))
        await store.add(_make_mod(id="b"))
        assert len(await store.list_all()) == 2


class TestListByProject:
    async def test_filters(self, store: InMemoryComponentModificationStore) -> None:
        await store.add(_make_mod(id="a", project_id="p1"))
        await store.add(_make_mod(id="b", project_id="p2"))
        result = await store.list_by_project("p1")
        assert len(result) == 1
        assert result[0]["project_id"] == "p1"


class TestUpdate:
    async def test_updates_fields(self, store: InMemoryComponentModificationStore) -> None:
        await store.add(_make_mod())
        result = await store.update("mod-1", {"status": "processing"})
        assert result is not None
        assert result["status"] == "processing"

    async def test_missing_returns_none(self, store: InMemoryComponentModificationStore) -> None:
        assert await store.update("nope", {"status": "failed"}) is None


class TestRemove:
    async def test_removes(self, store: InMemoryComponentModificationStore) -> None:
        await store.add(_make_mod())
        assert await store.remove("mod-1") is True
        assert await store.get("mod-1") is None

    async def test_missing_returns_false(self, store: InMemoryComponentModificationStore) -> None:
        assert await store.remove("nope") is False
