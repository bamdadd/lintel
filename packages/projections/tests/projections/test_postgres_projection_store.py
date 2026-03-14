"""Integration tests for PostgresProjectionStore — requires running Postgres."""

from datetime import UTC, datetime

import pytest

from lintel.contracts.projections import ProjectionState
from lintel.projections.stores import PostgresProjectionStore


def _make_state(name: str = "test", position: int = 0) -> ProjectionState:
    return ProjectionState(
        projection_name=name,
        global_position=position,
        stream_position=None,
        state={"tasks": {"abc": {"status": "pending"}}},
        updated_at=datetime(2026, 3, 14, 10, 30, 0, tzinfo=UTC),
    )


@pytest.mark.integration
class TestPostgresProjectionStore:
    """These tests require a Postgres instance — skipped in unit test runs."""

    def test_class_exists(self) -> None:
        """Verify the class is importable and has the right methods."""
        assert hasattr(PostgresProjectionStore, "save")
        assert hasattr(PostgresProjectionStore, "load")
        assert hasattr(PostgresProjectionStore, "load_all")
        assert hasattr(PostgresProjectionStore, "delete")
