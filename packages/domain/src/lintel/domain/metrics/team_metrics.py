"""MET-4: Team Metrics (Velocity, Throughput, Collaboration Index).

Provides ``TeamMetrics`` — a snapshot of team performance — and
``TeamMetricsCollector`` which aggregates metrics from work-item and
pipeline events over a sliding window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class TeamMetrics:
    """Point-in-time snapshot of team performance metrics."""

    velocity_points_per_week: float
    throughput_items_per_week: float
    collaboration_index: float
    active_contributors: int


# ---------------------------------------------------------------------------
# Internal event representations consumed by the collector
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletedWorkItem:
    """Lightweight record of a completed work item used for aggregation."""

    work_item_id: str
    completed_at: datetime
    points: float = 1.0
    assignee: str = ""


@dataclass(frozen=True)
class CompletedPipeline:
    """Lightweight record of a completed pipeline run."""

    run_id: str
    completed_at: datetime
    contributors: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

_DEFAULT_WINDOW_WEEKS = 4


class TeamMetricsCollector:
    """Aggregates work-item and pipeline events into ``TeamMetrics``.

    The collector maintains two append-only lists — completed work items and
    completed pipelines — and computes metrics over a configurable sliding
    window (default 4 weeks).

    **Collaboration index** is defined as the ratio of unique contributor
    pairs that co-occurred on pipeline runs to the theoretical maximum
    (``n*(n-1)/2`` for *n* active contributors).  When there are fewer than
    2 contributors the index is ``0.0``.
    """

    def __init__(self, window_weeks: int = _DEFAULT_WINDOW_WEEKS) -> None:
        self._window_weeks = window_weeks
        self._work_items: list[CompletedWorkItem] = []
        self._pipelines: list[CompletedPipeline] = []

    # -- ingest -------------------------------------------------------------

    def record_work_item(self, item: CompletedWorkItem) -> None:
        """Record a completed work item."""
        self._work_items.append(item)

    def record_pipeline(self, pipeline: CompletedPipeline) -> None:
        """Record a completed pipeline run."""
        self._pipelines.append(pipeline)

    # -- batch ingest -------------------------------------------------------

    def ingest_work_items(self, items: Sequence[CompletedWorkItem]) -> None:
        """Ingest a batch of completed work items."""
        self._work_items.extend(items)

    def ingest_pipelines(self, pipelines: Sequence[CompletedPipeline]) -> None:
        """Ingest a batch of completed pipeline runs."""
        self._pipelines.extend(pipelines)

    # -- compute ------------------------------------------------------------

    def compute(self, *, now: datetime | None = None) -> TeamMetrics:
        """Compute team metrics over the sliding window ending at *now*."""
        if now is None:
            now = datetime.now(tz=UTC)

        cutoff = now - timedelta(weeks=self._window_weeks)
        weeks = self._window_weeks

        # Filter to window
        items_in_window = [i for i in self._work_items if i.completed_at >= cutoff]
        pipelines_in_window = [p for p in self._pipelines if p.completed_at >= cutoff]

        # Velocity: total story points / weeks
        total_points = sum(i.points for i in items_in_window)
        velocity = total_points / weeks

        # Throughput: completed items / weeks
        throughput = len(items_in_window) / weeks

        # Active contributors: union of assignees + pipeline contributors
        contributors: set[str] = set()
        for item in items_in_window:
            if item.assignee:
                contributors.add(item.assignee)
        for pipeline in pipelines_in_window:
            contributors.update(c for c in pipeline.contributors if c)

        # Collaboration index
        collaboration = _collaboration_index(pipelines_in_window, contributors)

        return TeamMetrics(
            velocity_points_per_week=round(velocity, 2),
            throughput_items_per_week=round(throughput, 2),
            collaboration_index=round(collaboration, 2),
            active_contributors=len(contributors),
        )


def _collaboration_index(
    pipelines: list[CompletedPipeline],
    all_contributors: set[str],
) -> float:
    """Compute collaboration index from pipeline contributor overlap.

    Returns a value between 0.0 and 1.0.
    """
    n = len(all_contributors)
    if n < 2:
        return 0.0

    max_pairs = n * (n - 1) / 2

    observed_pairs: set[tuple[str, str]] = set()
    for pipeline in pipelines:
        contribs = sorted(c for c in pipeline.contributors if c)
        for i, a in enumerate(contribs):
            for b in contribs[i + 1 :]:
                observed_pairs.add((a, b))

    return len(observed_pairs) / max_pairs
