"""Tests for projection data models."""

from datetime import UTC, datetime

from lintel.projections.types import ProjectionState, ProjectionStatus


class TestProjectionState:
    def test_create_projection_state(self) -> None:
        state = ProjectionState(
            projection_name="task_backlog",
            global_position=42,
            stream_position=None,
            state={"tasks": {"abc": {"status": "pending"}}},
            updated_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
        )
        assert state.projection_name == "task_backlog"
        assert state.global_position == 42
        assert state.stream_position is None
        assert state.state == {"tasks": {"abc": {"status": "pending"}}}

    def test_projection_state_is_frozen(self) -> None:
        state = ProjectionState(
            projection_name="test",
            global_position=0,
            stream_position=None,
            state={},
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        try:
            state.projection_name = "other"  # type: ignore[misc]
            raise AssertionError("Should have raised")
        except AttributeError:
            pass

    def test_stream_position_optional(self) -> None:
        state = ProjectionState(
            projection_name="test",
            global_position=10,
            stream_position=5,
            state={},
            updated_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        assert state.stream_position == 5


class TestProjectionStatus:
    def test_create_projection_status(self) -> None:
        status = ProjectionStatus(
            name="task_backlog",
            status="running",
            global_position=100,
            lag=3,
            last_event_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
            events_processed=100,
        )
        assert status.name == "task_backlog"
        assert status.status == "running"
        assert status.lag == 3
        assert status.events_processed == 100

    def test_last_event_at_nullable(self) -> None:
        status = ProjectionStatus(
            name="empty",
            status="stopped",
            global_position=0,
            lag=0,
            last_event_at=None,
            events_processed=0,
        )
        assert status.last_event_at is None
