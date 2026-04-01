"""Tests for MetricsEngine, snapshot computation, and InMemoryMetricsStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lintel.domain.metrics.engine import (
    AgentMetricCollector,
    AgentMetrics,
    DoraMetricCollector,
    DoraMetrics,
    HumanMetricCollector,
    HumanMetrics,
    InMemoryMetricsStore,
    MetricsEngine,
    MetricsSnapshot,
    TeamMetricCollector,
    TeamMetrics,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

NOW = datetime.now(UTC)
YESTERDAY = NOW - timedelta(days=1)


def _agent_record(
    *,
    role: str = "coder",
    success: bool = True,
    duration_ms: int = 1000,
    project_id: str = "proj-1",
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "event_type": "AgentPerformanceComputed",
        "agent_role": role,
        "success": success,
        "duration_ms": duration_ms,
        "project_id": project_id,
        "occurred_at": (occurred_at or YESTERDAY).isoformat(),
    }


def _delivery_record(
    *,
    lead_time_seconds: float = 3600.0,
    is_failure: bool = False,
    restore_time_seconds: float = 0.0,
    project_id: str = "proj-1",
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "event_type": "DeliveryMetricComputed",
        "lead_time_seconds": lead_time_seconds,
        "is_failure": is_failure,
        "restore_time_seconds": restore_time_seconds,
        "project_id": project_id,
        "occurred_at": (occurred_at or YESTERDAY).isoformat(),
    }


def _human_record(
    *,
    approval_latency_seconds: float = 120.0,
    review_turnaround_seconds: float = 600.0,
    project_id: str = "proj-1",
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "event_type": "HumanPerformanceComputed",
        "approval_latency_seconds": approval_latency_seconds,
        "review_turnaround_seconds": review_turnaround_seconds,
        "project_id": project_id,
        "occurred_at": (occurred_at or YESTERDAY).isoformat(),
    }


def _work_item_record(
    *,
    team_id: str = "team-a",
    story_points: float = 3.0,
    project_id: str = "proj-1",
    occurred_at: datetime | None = None,
) -> dict[str, object]:
    return {
        "event_type": "WorkItemCompleted",
        "team_id": team_id,
        "story_points": story_points,
        "project_id": project_id,
        "occurred_at": (occurred_at or YESTERDAY).isoformat(),
    }


# ---------------------------------------------------------------------------
# Agent collector tests
# ---------------------------------------------------------------------------


class TestAgentMetricCollector:
    def test_collects_by_role(self) -> None:
        records = [
            _agent_record(role="coder", success=True, duration_ms=1000),
            _agent_record(role="coder", success=False, duration_ms=2000),
            _agent_record(role="reviewer", success=True, duration_ms=500),
        ]
        result = AgentMetricCollector().collect(
            records, project_id="proj-1", since=NOW - timedelta(days=7), until=NOW
        )
        assert len(result) == 2
        coder = next(m for m in result if m.agent_role == "coder")
        assert coder.tasks_completed == 1
        assert coder.tasks_failed == 1
        assert coder.success_rate == 0.5

    def test_filters_by_project(self) -> None:
        records = [
            _agent_record(project_id="proj-1"),
            _agent_record(project_id="proj-2"),
        ]
        result = AgentMetricCollector().collect(
            records, project_id="proj-1", since=NOW - timedelta(days=7), until=NOW
        )
        assert len(result) == 1

    def test_filters_by_time_window(self) -> None:
        old = NOW - timedelta(days=60)
        records = [
            _agent_record(occurred_at=old),
            _agent_record(occurred_at=YESTERDAY),
        ]
        result = AgentMetricCollector().collect(
            records, project_id="proj-1", since=NOW - timedelta(days=7), until=NOW
        )
        assert len(result) == 1


# ---------------------------------------------------------------------------
# DORA collector tests
# ---------------------------------------------------------------------------


class TestDoraMetricCollector:
    def test_computes_dora_metrics(self) -> None:
        records = [
            _delivery_record(lead_time_seconds=3600),
            _delivery_record(lead_time_seconds=7200, is_failure=True, restore_time_seconds=900),
        ]
        result = DoraMetricCollector().collect(
            records, project_id="proj-1", since=NOW - timedelta(days=7), until=NOW
        )
        assert isinstance(result, DoraMetrics)
        assert result.deployment_frequency > 0
        assert result.lead_time_seconds == 5400.0
        assert result.change_failure_rate == 0.5
        assert result.mttr_seconds == 900.0

    def test_empty_records(self) -> None:
        result = DoraMetricCollector().collect(
            [], project_id="proj-1", since=NOW - timedelta(days=7), until=NOW
        )
        assert result.deployment_frequency == 0.0


# ---------------------------------------------------------------------------
# Human collector tests
# ---------------------------------------------------------------------------


class TestHumanMetricCollector:
    def test_computes_human_metrics(self) -> None:
        records = [
            _human_record(approval_latency_seconds=100, review_turnaround_seconds=500),
            _human_record(approval_latency_seconds=200, review_turnaround_seconds=700),
        ]
        result = HumanMetricCollector().collect(
            records, project_id="proj-1", since=NOW - timedelta(days=7), until=NOW
        )
        assert isinstance(result, HumanMetrics)
        assert result.intervention_count == 2
        assert result.approval_latency_seconds == 150.0
        assert result.review_turnaround_seconds == 600.0


# ---------------------------------------------------------------------------
# Team collector tests
# ---------------------------------------------------------------------------


class TestTeamMetricCollector:
    def test_collects_by_team(self) -> None:
        records = [
            _work_item_record(team_id="team-a", story_points=3),
            _work_item_record(team_id="team-a", story_points=5),
            _work_item_record(team_id="team-b", story_points=2),
        ]
        result = TeamMetricCollector().collect(
            records, project_id="proj-1", since=NOW - timedelta(days=7), until=NOW
        )
        assert len(result) == 2
        team_a = next(t for t in result if t.team_id == "team-a")
        assert team_a.items_completed == 2


# ---------------------------------------------------------------------------
# InMemoryMetricsStore tests
# ---------------------------------------------------------------------------


class TestInMemoryMetricsStore:
    @pytest.fixture
    def store(self) -> InMemoryMetricsStore:
        return InMemoryMetricsStore()

    async def test_save_and_get(self, store: InMemoryMetricsStore) -> None:
        snap = MetricsSnapshot(snapshot_id="s1", project_id="proj-1")
        await store.save(snap)
        result = await store.get("s1")
        assert result is snap

    async def test_get_missing_returns_none(self, store: InMemoryMetricsStore) -> None:
        assert await store.get("missing") is None

    async def test_list_by_project(self, store: InMemoryMetricsStore) -> None:
        s1 = MetricsSnapshot(snapshot_id="s1", project_id="proj-1", captured_at=YESTERDAY)
        s2 = MetricsSnapshot(snapshot_id="s2", project_id="proj-1", captured_at=NOW)
        s3 = MetricsSnapshot(snapshot_id="s3", project_id="proj-2")
        await store.save(s1)
        await store.save(s2)
        await store.save(s3)

        results = await store.list_by_project("proj-1")
        assert len(results) == 2
        # Most recent first
        assert results[0].snapshot_id == "s2"

    async def test_list_by_project_with_time_window(self, store: InMemoryMetricsStore) -> None:
        old = NOW - timedelta(days=60)
        s1 = MetricsSnapshot(snapshot_id="s1", project_id="proj-1", captured_at=old)
        s2 = MetricsSnapshot(snapshot_id="s2", project_id="proj-1", captured_at=YESTERDAY)
        await store.save(s1)
        await store.save(s2)

        results = await store.list_by_project("proj-1", since=NOW - timedelta(days=7))
        assert len(results) == 1
        assert results[0].snapshot_id == "s2"

    async def test_list_respects_limit(self, store: InMemoryMetricsStore) -> None:
        for i in range(5):
            await store.save(
                MetricsSnapshot(
                    snapshot_id=f"s{i}",
                    project_id="proj-1",
                    captured_at=NOW - timedelta(hours=i),
                )
            )
        results = await store.list_by_project("proj-1", limit=2)
        assert len(results) == 2

    async def test_latest(self, store: InMemoryMetricsStore) -> None:
        s1 = MetricsSnapshot(snapshot_id="s1", project_id="proj-1", captured_at=YESTERDAY)
        s2 = MetricsSnapshot(snapshot_id="s2", project_id="proj-1", captured_at=NOW)
        await store.save(s1)
        await store.save(s2)
        result = await store.latest("proj-1")
        assert result is not None
        assert result.snapshot_id == "s2"

    async def test_latest_missing(self, store: InMemoryMetricsStore) -> None:
        assert await store.latest("proj-1") is None


# ---------------------------------------------------------------------------
# MetricsEngine integration tests
# ---------------------------------------------------------------------------


class TestMetricsEngine:
    @pytest.fixture
    def store(self) -> InMemoryMetricsStore:
        return InMemoryMetricsStore()

    @pytest.fixture
    def engine(self, store: InMemoryMetricsStore) -> MetricsEngine:
        return MetricsEngine(store=store)

    async def test_compute_snapshot_persists(
        self, engine: MetricsEngine, store: InMemoryMetricsStore
    ) -> None:
        records = [
            _agent_record(),
            _delivery_record(),
            _human_record(),
            _work_item_record(),
        ]
        snap = await engine.compute_snapshot(records, project_id="proj-1")
        assert snap.project_id == "proj-1"
        assert snap.window_days == 30
        # Was persisted
        assert await store.get(snap.snapshot_id) is snap

    async def test_compute_snapshot_no_persist(
        self, engine: MetricsEngine, store: InMemoryMetricsStore
    ) -> None:
        snap = await engine.compute_snapshot([], project_id="proj-1", persist=False)
        assert await store.get(snap.snapshot_id) is None

    async def test_compute_populates_all_categories(self, engine: MetricsEngine) -> None:
        records = [
            _agent_record(role="coder", success=True, duration_ms=500),
            _agent_record(role="coder", success=False, duration_ms=1500),
            _delivery_record(lead_time_seconds=3600),
            _human_record(approval_latency_seconds=120),
            _work_item_record(team_id="team-a", story_points=5),
        ]
        snap = await engine.compute_snapshot(records, project_id="proj-1")
        assert len(snap.agent_metrics) == 1
        assert snap.agent_metrics[0].agent_role == "coder"
        assert snap.dora_metrics.deployment_frequency > 0
        assert snap.human_metrics.intervention_count == 1
        assert len(snap.team_metrics) == 1

    async def test_list_and_latest(
        self, engine: MetricsEngine, store: InMemoryMetricsStore
    ) -> None:
        await engine.compute_snapshot([], project_id="proj-1", window_days=7)
        await engine.compute_snapshot([], project_id="proj-1", window_days=30)

        results = await engine.list_snapshots("proj-1")
        assert len(results) == 2

        latest = await engine.latest_snapshot("proj-1")
        assert latest is not None
        assert latest.window_days == 30

    async def test_get_snapshot(self, engine: MetricsEngine) -> None:
        snap = await engine.compute_snapshot([], project_id="proj-1")
        result = await engine.get_snapshot(snap.snapshot_id)
        assert result is snap

    async def test_custom_window_days(self, engine: MetricsEngine) -> None:
        snap = await engine.compute_snapshot([], project_id="proj-1", window_days=90)
        assert snap.window_days == 90


# ---------------------------------------------------------------------------
# Snapshot dataclass tests
# ---------------------------------------------------------------------------


class TestMetricsSnapshot:
    def test_to_dict(self) -> None:
        snap = MetricsSnapshot(
            snapshot_id="s1",
            project_id="proj-1",
            agent_metrics=(AgentMetrics(agent_role="coder", tasks_completed=5),),
            dora_metrics=DoraMetrics(deployment_frequency=1.5),
            human_metrics=HumanMetrics(intervention_count=3),
            team_metrics=(TeamMetrics(team_id="t1", items_completed=10),),
        )
        d = snap.to_dict()
        assert d["snapshot_id"] == "s1"
        assert d["project_id"] == "proj-1"
        assert len(d["agent_metrics"]) == 1
        assert d["dora_metrics"]["deployment_frequency"] == 1.5

    def test_defaults(self) -> None:
        snap = MetricsSnapshot()
        assert snap.agent_metrics == ()
        assert snap.team_metrics == ()
        assert snap.dora_metrics.deployment_frequency == 0.0
        assert snap.human_metrics.intervention_count == 0


class TestAgentMetricsSuccessRate:
    def test_zero_total(self) -> None:
        m = AgentMetrics(agent_role="x")
        assert m.success_rate == 0.0

    def test_all_success(self) -> None:
        m = AgentMetrics(agent_role="x", tasks_completed=5, tasks_failed=0)
        assert m.success_rate == 1.0
