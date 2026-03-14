"""Tests for ProjectionEngine position tracking, persistence, and status."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.projections import ProjectionState
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine
from lintel.infrastructure.projections.stores import InMemoryProjectionStore


class StubProjection:
    """Minimal projection for testing engine behaviour."""

    def __init__(self, projection_name: str = "stub") -> None:
        self._name = projection_name
        self._events: list[EventEnvelope] = []
        self._state: dict[str, Any] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def handled_event_types(self) -> set[str]:
        return {"TestEvent"}

    async def project(self, event: EventEnvelope) -> None:
        self._events.append(event)
        self._state[str(event.event_id)] = event.event_type

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._events.clear()
        self._state.clear()
        for e in events:
            await self.project(e)

    def get_state(self) -> dict[str, Any]:
        return dict(self._state)

    def restore_state(self, state: dict[str, Any]) -> None:
        self._state = dict(state)


def _make_event(position: int = 0) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type="TestEvent",
        schema_version=1,
        occurred_at=datetime.now(UTC),
        actor_type="system",
        actor_id="test",
        thread_ref=None,
        correlation_id=uuid4(),
        causation_id=uuid4(),
        payload={},
        idempotency_key=None,
        global_position=position,
    )


class TestEnginePositionTracking:
    async def test_position_starts_at_zero(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = StubProjection()
        await engine.register(proj)
        statuses = await engine.get_status()
        assert len(statuses) == 1
        assert statuses[0].global_position == 0
        assert statuses[0].events_processed == 0

    async def test_position_advances_on_project(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = StubProjection()
        await engine.register(proj)
        await engine.project(_make_event(position=5))
        await engine.project(_make_event(position=10))
        statuses = await engine.get_status()
        assert statuses[0].global_position == 10
        assert statuses[0].events_processed == 2


class TestEnginePersistence:
    async def test_persists_after_snapshot_interval(self) -> None:
        store = InMemoryProjectionStore()
        engine = InMemoryProjectionEngine(projection_store=store, snapshot_interval=2)
        proj = StubProjection("snap_test")
        await engine.register(proj)

        await engine.project(_make_event(position=1))
        assert await store.load("snap_test") is None  # not yet

        await engine.project(_make_event(position=2))
        saved = await store.load("snap_test")
        assert saved is not None
        assert saved.global_position == 2

    async def test_stop_flushes_state(self) -> None:
        store = InMemoryProjectionStore()
        engine = InMemoryProjectionEngine(projection_store=store, snapshot_interval=999)
        proj = StubProjection("flush_test")
        await engine.register(proj)
        await engine.project(_make_event(position=1))
        assert await store.load("flush_test") is None  # interval not reached

        await engine.stop()
        saved = await store.load("flush_test")
        assert saved is not None
        assert saved.global_position == 1


class TestEngineRestore:
    async def test_start_restores_from_store(self) -> None:
        store = InMemoryProjectionStore()
        await store.save(
            ProjectionState(
                projection_name="restore_test",
                global_position=50,
                stream_position=None,
                state={"existing": "data"},
                updated_at=datetime.now(UTC),
            )
        )

        engine = InMemoryProjectionEngine(projection_store=store)
        proj = StubProjection("restore_test")
        await engine.register(proj)
        await engine.start()

        assert proj.get_state() == {"existing": "data"}
        statuses = await engine.get_status()
        assert statuses[0].global_position == 50


class TestEngineResetClearsStore:
    async def test_reset_all_clears_persisted_state(self) -> None:
        store = InMemoryProjectionStore()
        engine = InMemoryProjectionEngine(projection_store=store, snapshot_interval=1)
        proj = StubProjection("reset_test")
        await engine.register(proj)
        await engine.project(_make_event(position=1))
        assert await store.load("reset_test") is not None

        await engine.reset_all()
        assert await store.load("reset_test") is None


class TestEngineStatus:
    async def test_get_status_returns_all_projections(self) -> None:
        engine = InMemoryProjectionEngine()
        await engine.register(StubProjection("a"))
        await engine.register(StubProjection("b"))
        statuses = await engine.get_status()
        assert len(statuses) == 2
        names = {s.name for s in statuses}
        assert names == {"a", "b"}

    async def test_status_shows_running_after_start(self) -> None:
        engine = InMemoryProjectionEngine()
        proj = StubProjection()
        await engine.register(proj)
        statuses = await engine.get_status()
        assert statuses[0].status == "stopped"

        await engine.start()
        statuses = await engine.get_status()
        assert statuses[0].status == "running"
