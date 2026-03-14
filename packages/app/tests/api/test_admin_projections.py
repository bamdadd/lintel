"""Tests for GET /admin/projections endpoint."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from lintel.contracts.projections import ProjectionStatus
from lintel.projections.engine import InMemoryProjectionEngine


class TestAdminProjectionsEndpoint:
    async def test_get_projection_status_returns_list(self) -> None:
        """Test the endpoint logic directly (no HTTP server needed)."""
        from lintel.api.routes.admin import get_projection_status

        mock_engine = AsyncMock(spec=InMemoryProjectionEngine)
        mock_engine.get_status.return_value = [
            ProjectionStatus(
                name="task_backlog",
                status="running",
                global_position=100,
                lag=2,
                last_event_at=datetime(2026, 3, 14, 10, 0, tzinfo=UTC),
                events_processed=100,
            ),
            ProjectionStatus(
                name="audit",
                status="running",
                global_position=95,
                lag=7,
                last_event_at=None,
                events_processed=95,
            ),
        ]

        result = await get_projection_status(engine=mock_engine)

        assert len(result) == 2
        assert result[0]["name"] == "task_backlog"
        assert result[0]["status"] == "running"
        assert result[0]["global_position"] == 100
        assert result[0]["last_event_at"] == "2026-03-14T10:00:00+00:00"
        assert result[1]["name"] == "audit"
        assert result[1]["last_event_at"] is None
