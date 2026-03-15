"""Tests for InMemoryProjectionStore."""

from datetime import UTC, datetime

from lintel.projections.stores import InMemoryProjectionStore
from lintel.projections.types import ProjectionState


def _make_state(name: str = "test", position: int = 0) -> ProjectionState:
    return ProjectionState(
        projection_name=name,
        global_position=position,
        stream_position=None,
        state={"key": "value"},
        updated_at=datetime(2026, 3, 14, tzinfo=UTC),
    )


class TestInMemoryProjectionStore:
    async def test_save_and_load(self) -> None:
        store = InMemoryProjectionStore()
        state = _make_state("backlog", 42)
        await store.save(state)
        loaded = await store.load("backlog")
        assert loaded == state

    async def test_load_missing_returns_none(self) -> None:
        store = InMemoryProjectionStore()
        assert await store.load("missing") is None

    async def test_save_overwrites(self) -> None:
        store = InMemoryProjectionStore()
        await store.save(_make_state("a", 1))
        await store.save(_make_state("a", 2))
        loaded = await store.load("a")
        assert loaded is not None
        assert loaded.global_position == 2

    async def test_load_all(self) -> None:
        store = InMemoryProjectionStore()
        await store.save(_make_state("a", 1))
        await store.save(_make_state("b", 2))
        all_states = await store.load_all()
        assert len(all_states) == 2
        names = {s.projection_name for s in all_states}
        assert names == {"a", "b"}

    async def test_delete(self) -> None:
        store = InMemoryProjectionStore()
        await store.save(_make_state("a"))
        await store.delete("a")
        assert await store.load("a") is None

    async def test_delete_missing_is_noop(self) -> None:
        store = InMemoryProjectionStore()
        await store.delete("nope")  # should not raise
