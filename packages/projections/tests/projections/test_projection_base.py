"""Unit tests for ProjectionBase dispatch and position tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from lintel.contracts.events import EventEnvelope
from lintel.contracts.types import ActorType
from lintel.projections.base import ProjectionBase, _to_snake_case


def _make_event(event_type: str = "TestEvent", position: int | None = None) -> EventEnvelope:
    return EventEnvelope(
        event_id=uuid4(),
        event_type=event_type,
        schema_version=1,
        occurred_at=datetime.now(UTC),
        actor_type=ActorType.SYSTEM,
        actor_id="test",
        correlation_id=uuid4(),
        payload={},
        global_position=position,
    )


class _TestProjection(ProjectionBase):
    """Concrete test subclass with a few typed handlers."""

    def __init__(self) -> None:
        super().__init__()
        self.handled: list[EventEnvelope] = []
        self.saved_positions: list[int] = []

    def get_name(self) -> str:
        return "test-projection"

    async def on_test_event(self, envelope: EventEnvelope) -> None:
        self.handled.append(envelope)

    async def on_workflow_started(self, envelope: EventEnvelope) -> None:
        self.handled.append(envelope)

    async def save_position(self, position: int) -> None:
        self.saved_positions.append(position)


class TestToSnakeCase:
    def test_simple(self) -> None:
        assert _to_snake_case("TestEvent") == "test_event"

    def test_multi_word(self) -> None:
        assert _to_snake_case("ThreadMessageReceived") == "thread_message_received"

    def test_single_word(self) -> None:
        assert _to_snake_case("Event") == "event"

    def test_acronym(self) -> None:
        assert _to_snake_case("MCPServerRegistered") == "mcp_server_registered"


class TestProjectionBase:
    async def test_dispatches_to_matching_handler(self) -> None:
        proj = _TestProjection()
        event = _make_event("TestEvent", position=1)
        await proj.handle(event)

        assert len(proj.handled) == 1
        assert proj.handled[0].event_id == event.event_id

    async def test_ignores_unhandled_event_types(self) -> None:
        proj = _TestProjection()
        event = _make_event("UnknownEvent", position=1)
        await proj.handle(event)

        assert len(proj.handled) == 0

    async def test_updates_last_position(self) -> None:
        proj = _TestProjection()
        await proj.handle(_make_event("TestEvent", position=5))
        assert proj.last_position == 5

        await proj.handle(_make_event("TestEvent", position=10))
        assert proj.last_position == 10

    async def test_position_updated_even_for_unhandled_events(self) -> None:
        proj = _TestProjection()
        await proj.handle(_make_event("UnknownEvent", position=7))
        assert proj.last_position == 7

    async def test_none_position_does_not_update(self) -> None:
        proj = _TestProjection()
        proj.last_position = 3
        await proj.handle(_make_event("TestEvent", position=None))
        assert proj.last_position == 3

    async def test_save_position_called(self) -> None:
        proj = _TestProjection()
        await proj.handle(_make_event("TestEvent", position=42))
        assert 42 in proj.saved_positions

    async def test_multiple_event_types(self) -> None:
        proj = _TestProjection()
        await proj.handle(_make_event("TestEvent", position=1))
        await proj.handle(_make_event("WorkflowStarted", position=2))

        assert len(proj.handled) == 2
        assert proj.last_position == 2

    async def test_get_name(self) -> None:
        proj = _TestProjection()
        assert proj.get_name() == "test-projection"

    async def test_initial_last_position_is_zero(self) -> None:
        proj = _TestProjection()
        assert proj.last_position == 0
