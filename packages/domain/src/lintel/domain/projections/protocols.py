"""Projection protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.projections import ProjectionState, ProjectionStatus


class Projection(Protocol):
    """A projection that builds a read model from events."""

    @property
    def name(self) -> str: ...

    @property
    def handled_event_types(self) -> set[str]: ...

    async def project(self, event: EventEnvelope) -> None: ...

    async def rebuild(self, events: list[EventEnvelope]) -> None: ...

    def get_state(self) -> dict[str, Any]: ...

    def restore_state(self, state: dict[str, Any]) -> None: ...


class ProjectionStore(Protocol):
    """Persists projection state for recovery after restart."""

    async def save(self, state: ProjectionState) -> None: ...

    async def load(self, projection_name: str) -> ProjectionState | None: ...

    async def load_all(self) -> list[ProjectionState]: ...

    async def delete(self, projection_name: str) -> None: ...


class ProjectionEngine(Protocol):
    """Dispatches events to registered projections."""

    async def register(self, projection: Projection) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def project(self, event: EventEnvelope) -> None: ...

    async def rebuild_all(self, stream_id: str) -> None: ...

    async def get_status(self) -> list[ProjectionStatus]: ...

    async def reset_all(self) -> None: ...
