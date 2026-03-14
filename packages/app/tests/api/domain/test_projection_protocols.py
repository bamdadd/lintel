"""Tests that verify Protocol structural compliance."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.projections import (
        Projection,
        ProjectionEngine,
        ProjectionState,
        ProjectionStatus,
        ProjectionStore,
    )


class FakeProjection:
    @property
    def name(self) -> str:
        return "fake"

    @property
    def handled_event_types(self) -> set[str]:
        return {"TestEvent"}

    async def project(self, event: EventEnvelope) -> None:
        pass

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        pass

    def get_state(self) -> dict[str, Any]:
        return {}

    def restore_state(self, state: dict[str, Any]) -> None:
        pass


class FakeProjectionStore:
    async def save(self, state: ProjectionState) -> None:
        pass

    async def load(self, projection_name: str) -> ProjectionState | None:
        return None

    async def load_all(self) -> list[ProjectionState]:
        return []

    async def delete(self, projection_name: str) -> None:
        pass


class FakeProjectionEngine:
    async def register(self, projection: Projection) -> None:
        pass

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def project(self, event: EventEnvelope) -> None:
        pass

    async def rebuild_all(self, stream_id: str) -> None:
        pass

    async def get_status(self) -> list[ProjectionStatus]:
        return []

    async def reset_all(self) -> None:
        pass


def test_fake_projection_satisfies_protocol() -> None:
    p: Projection = FakeProjection()
    assert p.name == "fake"
    assert p.handled_event_types == {"TestEvent"}
    assert p.get_state() == {}


def test_fake_store_satisfies_protocol() -> None:
    s: ProjectionStore = FakeProjectionStore()
    assert s is not None


def test_fake_engine_satisfies_protocol() -> None:
    e: ProjectionEngine = FakeProjectionEngine()
    assert e is not None
