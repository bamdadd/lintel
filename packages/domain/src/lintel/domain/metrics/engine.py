"""Metrics computation engine (MET-6).

Coordinates metric collectors, produces point-in-time snapshots, and supports
time-windowed queries.  Four metric categories are aggregated:

* **Agent metrics** — per-agent performance (tasks completed, avg duration, success rate)
* **DORA metrics** — deployment frequency, lead time, change failure rate, MTTR
* **Human metrics** — human intervention rate, approval latency, review turnaround
* **Team metrics** — throughput, velocity, utilisation across teams
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

# ---------------------------------------------------------------------------
# Metric data types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AgentMetrics:
    """Performance counters for a single agent role."""

    agent_role: str
    tasks_completed: int = 0
    tasks_failed: int = 0
    avg_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return (self.tasks_completed / total) if total > 0 else 0.0


@dataclass(frozen=True)
class DoraMetrics:
    """DORA four key metrics for a project."""

    deployment_frequency: float = 0.0  # deploys per day
    lead_time_seconds: float = 0.0  # commit-to-deploy
    change_failure_rate: float = 0.0  # ratio 0..1
    mttr_seconds: float = 0.0  # mean time to restore


@dataclass(frozen=True)
class HumanMetrics:
    """Human-in-the-loop performance metrics."""

    intervention_count: int = 0
    approval_latency_seconds: float = 0.0
    review_turnaround_seconds: float = 0.0


@dataclass(frozen=True)
class TeamMetrics:
    """Aggregate team throughput metrics."""

    team_id: str
    items_completed: int = 0
    velocity: float = 0.0  # story points per sprint/period
    utilisation: float = 0.0  # ratio 0..1


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MetricsSnapshot:
    """Point-in-time snapshot holding all metric categories."""

    snapshot_id: str = field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    window_days: int = 30
    agent_metrics: tuple[AgentMetrics, ...] = ()
    dora_metrics: DoraMetrics = field(default_factory=DoraMetrics)
    human_metrics: HumanMetrics = field(default_factory=HumanMetrics)
    team_metrics: tuple[TeamMetrics, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


# ---------------------------------------------------------------------------
# Collector protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class MetricCollector(Protocol):
    """Pluggable collector that extracts one metric category from raw data."""

    def collect(
        self,
        records: list[dict[str, Any]],
        *,
        project_id: str,
        since: datetime,
        until: datetime,
    ) -> object:
        """Return the metric dataclass for this category."""
        ...


# ---------------------------------------------------------------------------
# Built-in collectors
# ---------------------------------------------------------------------------


class AgentMetricCollector:
    """Collects agent performance from ``AgentPerformanceComputed`` records."""

    def collect(
        self,
        records: list[dict[str, Any]],
        *,
        project_id: str,
        since: datetime,
        until: datetime,
    ) -> tuple[AgentMetrics, ...]:
        by_role: dict[str, dict[str, Any]] = {}
        for rec in records:
            if rec.get("event_type") != "AgentPerformanceComputed":
                continue
            ts = _parse_ts(rec.get("occurred_at"))
            if ts < since or ts > until:
                continue
            if project_id and rec.get("project_id", "") != project_id:
                continue
            role = rec.get("agent_role", "unknown")
            agg = by_role.setdefault(role, {"ok": 0, "fail": 0, "dur_sum": 0.0})
            if rec.get("success", True):
                agg["ok"] += 1
            else:
                agg["fail"] += 1
            agg["dur_sum"] += float(rec.get("duration_ms", 0))

        results: list[AgentMetrics] = []
        for role, agg in sorted(by_role.items()):
            total = agg["ok"] + agg["fail"]
            avg_dur = (agg["dur_sum"] / total) if total > 0 else 0.0
            results.append(
                AgentMetrics(
                    agent_role=role,
                    tasks_completed=agg["ok"],
                    tasks_failed=agg["fail"],
                    avg_duration_ms=round(avg_dur, 2),
                )
            )
        return tuple(results)


class DoraMetricCollector:
    """Collects DORA metrics from ``DeliveryMetricComputed`` records."""

    def collect(
        self,
        records: list[dict[str, Any]],
        *,
        project_id: str,
        since: datetime,
        until: datetime,
    ) -> DoraMetrics:
        deploy_count = 0
        lead_times: list[float] = []
        failures = 0
        total_deploys = 0
        restore_times: list[float] = []

        for rec in records:
            if rec.get("event_type") != "DeliveryMetricComputed":
                continue
            ts = _parse_ts(rec.get("occurred_at"))
            if ts < since or ts > until:
                continue
            if project_id and rec.get("project_id", "") != project_id:
                continue
            deploy_count += 1
            total_deploys += 1
            if lt := rec.get("lead_time_seconds"):
                lead_times.append(float(lt))
            if rec.get("is_failure", False):
                failures += 1
            if rt := rec.get("restore_time_seconds"):
                restore_times.append(float(rt))

        window_days = max((until - since).days, 1)
        return DoraMetrics(
            deployment_frequency=round(deploy_count / window_days, 4),
            lead_time_seconds=round(sum(lead_times) / len(lead_times), 2) if lead_times else 0.0,
            change_failure_rate=round(failures / total_deploys, 4) if total_deploys else 0.0,
            mttr_seconds=round(sum(restore_times) / len(restore_times), 2)
            if restore_times
            else 0.0,
        )


class HumanMetricCollector:
    """Collects human-in-the-loop metrics from ``HumanPerformanceComputed`` records."""

    def collect(
        self,
        records: list[dict[str, Any]],
        *,
        project_id: str,
        since: datetime,
        until: datetime,
    ) -> HumanMetrics:
        count = 0
        approval_latencies: list[float] = []
        review_turnarounds: list[float] = []

        for rec in records:
            if rec.get("event_type") != "HumanPerformanceComputed":
                continue
            ts = _parse_ts(rec.get("occurred_at"))
            if ts < since or ts > until:
                continue
            if project_id and rec.get("project_id", "") != project_id:
                continue
            count += 1
            if al := rec.get("approval_latency_seconds"):
                approval_latencies.append(float(al))
            if rt := rec.get("review_turnaround_seconds"):
                review_turnarounds.append(float(rt))

        return HumanMetrics(
            intervention_count=count,
            approval_latency_seconds=round(sum(approval_latencies) / len(approval_latencies), 2)
            if approval_latencies
            else 0.0,
            review_turnaround_seconds=round(sum(review_turnarounds) / len(review_turnarounds), 2)
            if review_turnarounds
            else 0.0,
        )


class TeamMetricCollector:
    """Collects team throughput from work-item completion records."""

    def collect(
        self,
        records: list[dict[str, Any]],
        *,
        project_id: str,
        since: datetime,
        until: datetime,
    ) -> tuple[TeamMetrics, ...]:
        by_team: dict[str, dict[str, Any]] = {}
        for rec in records:
            if rec.get("event_type") not in {
                "WorkItemCompleted",
                "WorkItemClosed",
            }:
                continue
            ts = _parse_ts(rec.get("occurred_at"))
            if ts < since or ts > until:
                continue
            if project_id and rec.get("project_id", "") != project_id:
                continue
            team_id = rec.get("team_id", "default")
            agg = by_team.setdefault(team_id, {"items": 0, "points": 0.0})
            agg["items"] += 1
            agg["points"] += float(rec.get("story_points", 0))

        window_days = max((until - since).days, 1)
        results: list[TeamMetrics] = []
        for team_id, agg in sorted(by_team.items()):
            results.append(
                TeamMetrics(
                    team_id=team_id,
                    items_completed=agg["items"],
                    velocity=round(agg["points"] / (window_days / 7), 2) if agg["points"] else 0.0,
                    utilisation=0.0,  # requires capacity data not yet available
                )
            )
        return tuple(results)


# ---------------------------------------------------------------------------
# Store protocol + in-memory implementation
# ---------------------------------------------------------------------------


@runtime_checkable
class MetricsStore(Protocol):
    """Persistence layer for metrics snapshots."""

    async def save(self, snapshot: MetricsSnapshot) -> None: ...

    async def get(self, snapshot_id: str) -> MetricsSnapshot | None: ...

    async def list_by_project(
        self,
        project_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[MetricsSnapshot]: ...

    async def latest(self, project_id: str) -> MetricsSnapshot | None: ...


class InMemoryMetricsStore:
    """Dict-backed ``MetricsStore`` for tests and dev."""

    def __init__(self) -> None:
        self._snapshots: dict[str, MetricsSnapshot] = {}

    async def save(self, snapshot: MetricsSnapshot) -> None:
        self._snapshots[snapshot.snapshot_id] = snapshot

    async def get(self, snapshot_id: str) -> MetricsSnapshot | None:
        return self._snapshots.get(snapshot_id)

    async def list_by_project(
        self,
        project_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[MetricsSnapshot]:
        results: list[MetricsSnapshot] = []
        for snap in self._snapshots.values():
            if snap.project_id != project_id:
                continue
            if since and snap.captured_at < since:
                continue
            if until and snap.captured_at > until:
                continue
            results.append(snap)
        results.sort(key=lambda s: s.captured_at, reverse=True)
        return results[:limit]

    async def latest(self, project_id: str) -> MetricsSnapshot | None:
        candidates = [s for s in self._snapshots.values() if s.project_id == project_id]
        if not candidates:
            return None
        return max(candidates, key=lambda s: s.captured_at)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class MetricsEngine:
    """Coordinates metric collectors and produces snapshots.

    Usage::

        engine = MetricsEngine(store=InMemoryMetricsStore())
        snapshot = await engine.compute_snapshot(
            records=raw_event_dicts,
            project_id="proj-1",
            window_days=30,
        )
    """

    def __init__(
        self,
        *,
        store: MetricsStore,
        agent_collector: AgentMetricCollector | None = None,
        dora_collector: DoraMetricCollector | None = None,
        human_collector: HumanMetricCollector | None = None,
        team_collector: TeamMetricCollector | None = None,
    ) -> None:
        self._store = store
        self._agent_collector = agent_collector or AgentMetricCollector()
        self._dora_collector = dora_collector or DoraMetricCollector()
        self._human_collector = human_collector or HumanMetricCollector()
        self._team_collector = team_collector or TeamMetricCollector()

    async def compute_snapshot(
        self,
        records: list[dict[str, Any]],
        *,
        project_id: str = "",
        window_days: int = 30,
        persist: bool = True,
    ) -> MetricsSnapshot:
        """Compute a snapshot from raw event records and optionally persist it."""
        now = datetime.now(UTC)
        since = now - timedelta(days=window_days)

        agent = self._agent_collector.collect(
            records, project_id=project_id, since=since, until=now
        )
        dora = self._dora_collector.collect(records, project_id=project_id, since=since, until=now)
        human = self._human_collector.collect(
            records, project_id=project_id, since=since, until=now
        )
        team = self._team_collector.collect(records, project_id=project_id, since=since, until=now)

        snapshot = MetricsSnapshot(
            project_id=project_id,
            captured_at=now,
            window_days=window_days,
            agent_metrics=agent,
            dora_metrics=dora,
            human_metrics=human,
            team_metrics=team,
        )

        if persist:
            await self._store.save(snapshot)

        return snapshot

    async def get_snapshot(self, snapshot_id: str) -> MetricsSnapshot | None:
        """Retrieve a previously stored snapshot."""
        return await self._store.get(snapshot_id)

    async def list_snapshots(
        self,
        project_id: str,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 100,
    ) -> list[MetricsSnapshot]:
        """Query snapshots for a project within an optional time window."""
        return await self._store.list_by_project(project_id, since=since, until=until, limit=limit)

    async def latest_snapshot(self, project_id: str) -> MetricsSnapshot | None:
        """Return the most recent snapshot for a project."""
        return await self._store.latest(project_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_ts(value: str | datetime | None) -> datetime:
    """Parse a timestamp from string or datetime, defaulting to epoch."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value)
    return datetime.min.replace(tzinfo=UTC)
