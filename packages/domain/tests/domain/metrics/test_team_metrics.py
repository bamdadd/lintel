"""Tests for MET-4: Team Metrics (Velocity, Throughput, Collaboration Index)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lintel.domain.metrics.team_metrics import (
    CompletedPipeline,
    CompletedWorkItem,
    TeamMetrics,
    TeamMetricsCollector,
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


class TestTeamMetricsDataclass:
    def test_frozen(self) -> None:
        m = TeamMetrics(
            velocity_points_per_week=5.0,
            throughput_items_per_week=3.0,
            collaboration_index=0.5,
            active_contributors=4,
        )
        assert m.velocity_points_per_week == 5.0
        assert m.active_contributors == 4

    def test_equality(self) -> None:
        kwargs = {
            "velocity_points_per_week": 1.0,
            "throughput_items_per_week": 2.0,
            "collaboration_index": 0.3,
            "active_contributors": 2,
        }
        assert TeamMetrics(**kwargs) == TeamMetrics(**kwargs)


class TestTeamMetricsCollector:
    def test_empty_collector_returns_zeros(self) -> None:
        collector = TeamMetricsCollector()
        metrics = collector.compute(now=_utcnow())
        assert metrics.velocity_points_per_week == 0.0
        assert metrics.throughput_items_per_week == 0.0
        assert metrics.collaboration_index == 0.0
        assert metrics.active_contributors == 0

    def test_velocity_and_throughput(self) -> None:
        now = _utcnow()
        collector = TeamMetricsCollector(window_weeks=2)

        # 3 items, 5 total points, over 2-week window
        for i in range(3):
            collector.record_work_item(
                CompletedWorkItem(
                    work_item_id=f"wi-{i}",
                    completed_at=now - timedelta(days=i),
                    points=2.0 if i == 0 else 1.5,
                    assignee="alice",
                )
            )

        metrics = collector.compute(now=now)
        # total points = 2.0 + 1.5 + 1.5 = 5.0, / 2 weeks = 2.5
        assert metrics.velocity_points_per_week == 2.5
        # 3 items / 2 weeks = 1.5
        assert metrics.throughput_items_per_week == 1.5

    def test_items_outside_window_excluded(self) -> None:
        now = _utcnow()
        collector = TeamMetricsCollector(window_weeks=1)

        # One item inside window, one outside
        collector.record_work_item(
            CompletedWorkItem(
                work_item_id="recent",
                completed_at=now - timedelta(days=1),
                points=3.0,
                assignee="bob",
            )
        )
        collector.record_work_item(
            CompletedWorkItem(
                work_item_id="old",
                completed_at=now - timedelta(weeks=2),
                points=10.0,
                assignee="bob",
            )
        )

        metrics = collector.compute(now=now)
        assert metrics.velocity_points_per_week == 3.0
        assert metrics.throughput_items_per_week == 1.0

    def test_active_contributors_from_items_and_pipelines(self) -> None:
        now = _utcnow()
        collector = TeamMetricsCollector(window_weeks=4)

        collector.record_work_item(
            CompletedWorkItem(
                work_item_id="wi-1",
                completed_at=now,
                assignee="alice",
            )
        )
        collector.record_pipeline(
            CompletedPipeline(
                run_id="run-1",
                completed_at=now,
                contributors=("bob", "charlie"),
            )
        )

        metrics = collector.compute(now=now)
        assert metrics.active_contributors == 3

    def test_collaboration_index_full(self) -> None:
        """All contributors co-occur on same pipeline => index = 1.0."""
        now = _utcnow()
        collector = TeamMetricsCollector(window_weeks=4)

        collector.record_pipeline(
            CompletedPipeline(
                run_id="run-1",
                completed_at=now,
                contributors=("alice", "bob", "charlie"),
            )
        )

        metrics = collector.compute(now=now)
        # 3 contributors, 3 observed pairs, max 3 => 1.0
        assert metrics.collaboration_index == 1.0
        assert metrics.active_contributors == 3

    def test_collaboration_index_partial(self) -> None:
        """Contributors only partially overlap across pipelines."""
        now = _utcnow()
        collector = TeamMetricsCollector(window_weeks=4)

        collector.record_pipeline(
            CompletedPipeline(
                run_id="run-1",
                completed_at=now,
                contributors=("alice", "bob"),
            )
        )
        collector.record_pipeline(
            CompletedPipeline(
                run_id="run-2",
                completed_at=now,
                contributors=("charlie",),
            )
        )

        metrics = collector.compute(now=now)
        # 3 contributors, max_pairs=3, observed=(alice,bob) => 1/3 ≈ 0.33
        assert metrics.collaboration_index == 0.33

    def test_collaboration_index_single_contributor(self) -> None:
        """Fewer than 2 contributors => collaboration index 0."""
        now = _utcnow()
        collector = TeamMetricsCollector(window_weeks=4)

        collector.record_work_item(
            CompletedWorkItem(
                work_item_id="wi-1",
                completed_at=now,
                assignee="alice",
            )
        )

        metrics = collector.compute(now=now)
        assert metrics.collaboration_index == 0.0

    def test_batch_ingest(self) -> None:
        now = _utcnow()
        collector = TeamMetricsCollector(window_weeks=1)

        items = [
            CompletedWorkItem(
                work_item_id=f"wi-{i}",
                completed_at=now,
                points=1.0,
                assignee="alice",
            )
            for i in range(4)
        ]
        collector.ingest_work_items(items)

        pipelines = [
            CompletedPipeline(
                run_id="run-1",
                completed_at=now,
                contributors=("alice", "bob"),
            )
        ]
        collector.ingest_pipelines(pipelines)

        metrics = collector.compute(now=now)
        assert metrics.throughput_items_per_week == 4.0
        assert metrics.velocity_points_per_week == 4.0
        assert metrics.active_contributors == 2

    def test_default_now(self) -> None:
        """Compute without explicit now should not raise."""
        collector = TeamMetricsCollector()
        metrics = collector.compute()
        assert metrics.active_contributors == 0
