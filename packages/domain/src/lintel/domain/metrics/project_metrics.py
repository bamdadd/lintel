"""REQ-030: Project Commit & PR Metrics Dashboard.

Provides ``CommitMetrics``, ``PRMetrics``, and ``ProjectMetricsDashboard``
frozen dataclasses, plus ``ProjectMetricsCollector`` which computes metrics
from raw commit and pull-request data over a configurable time window.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence


# ---------------------------------------------------------------------------
# Input records
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitRecord:
    """Lightweight record of a single commit used for aggregation."""

    sha: str
    author: str
    committed_at: datetime
    lines_added: int = 0
    lines_removed: int = 0


@dataclass(frozen=True)
class PRRecord:
    """Lightweight record of a pull request used for aggregation."""

    pr_id: str
    author: str
    created_at: datetime
    merged_at: datetime | None = None
    review_cycles: int = 1


# ---------------------------------------------------------------------------
# Output metrics
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CommitMetrics:
    """Aggregated commit metrics over a time window."""

    total_commits: int
    commits_per_day: float
    avg_lines_changed: float
    top_contributors: tuple[str, ...]


@dataclass(frozen=True)
class PRMetrics:
    """Aggregated pull-request metrics over a time window."""

    total_prs: int
    avg_merge_time_hours: float
    avg_review_cycles: float
    merge_rate: float


@dataclass(frozen=True)
class ProjectMetricsDashboard:
    """Combined project metrics dashboard for a time window."""

    project_id: str
    window_start: datetime
    window_end: datetime
    commit_metrics: CommitMetrics
    pr_metrics: PRMetrics


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

_DEFAULT_WINDOW_DAYS = 30
_TOP_CONTRIBUTORS_LIMIT = 5


class ProjectMetricsCollector:
    """Computes project-level commit and PR metrics from raw records.

    Usage::

        collector = ProjectMetricsCollector(project_id="proj-1")
        collector.ingest_commits(commits)
        collector.ingest_prs(prs)
        dashboard = collector.compute(window_days=30)
    """

    def __init__(self, project_id: str) -> None:
        self._project_id = project_id
        self._commits: list[CommitRecord] = []
        self._prs: list[PRRecord] = []

    # -- ingest -------------------------------------------------------------

    def record_commit(self, commit: CommitRecord) -> None:
        """Record a single commit."""
        self._commits.append(commit)

    def record_pr(self, pr: PRRecord) -> None:
        """Record a single pull request."""
        self._prs.append(pr)

    def ingest_commits(self, commits: Sequence[CommitRecord]) -> None:
        """Ingest a batch of commits."""
        self._commits.extend(commits)

    def ingest_prs(self, prs: Sequence[PRRecord]) -> None:
        """Ingest a batch of pull requests."""
        self._prs.extend(prs)

    # -- compute ------------------------------------------------------------

    def compute(
        self,
        *,
        window_days: int = _DEFAULT_WINDOW_DAYS,
        now: datetime | None = None,
    ) -> ProjectMetricsDashboard:
        """Compute project metrics over the given window ending at *now*."""
        if now is None:
            now = datetime.now(tz=UTC)

        window_start = now - timedelta(days=window_days)

        commits_in_window = [c for c in self._commits if c.committed_at >= window_start]
        prs_in_window = [p for p in self._prs if p.created_at >= window_start]

        return ProjectMetricsDashboard(
            project_id=self._project_id,
            window_start=window_start,
            window_end=now,
            commit_metrics=_compute_commit_metrics(commits_in_window, window_days),
            pr_metrics=_compute_pr_metrics(prs_in_window),
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_commit_metrics(
    commits: list[CommitRecord],
    window_days: int,
) -> CommitMetrics:
    total = len(commits)
    commits_per_day = total / max(window_days, 1)

    if total == 0:
        return CommitMetrics(
            total_commits=0,
            commits_per_day=0.0,
            avg_lines_changed=0.0,
            top_contributors=(),
        )

    total_lines = sum(c.lines_added + c.lines_removed for c in commits)
    avg_lines = total_lines / total

    # Top contributors by commit count
    counts: dict[str, int] = {}
    for c in commits:
        counts[c.author] = counts.get(c.author, 0) + 1
    sorted_authors = sorted(counts, key=lambda a: counts[a], reverse=True)
    top = tuple(sorted_authors[:_TOP_CONTRIBUTORS_LIMIT])

    return CommitMetrics(
        total_commits=total,
        commits_per_day=round(commits_per_day, 2),
        avg_lines_changed=round(avg_lines, 2),
        top_contributors=top,
    )


def _compute_pr_metrics(prs: list[PRRecord]) -> PRMetrics:
    total = len(prs)
    if total == 0:
        return PRMetrics(
            total_prs=0,
            avg_merge_time_hours=0.0,
            avg_review_cycles=0.0,
            merge_rate=0.0,
        )

    merged = [p for p in prs if p.merged_at is not None]
    merge_rate = len(merged) / total

    if merged:
        merge_times_hours = [
            (p.merged_at - p.created_at).total_seconds() / 3600  # type: ignore[operator]
            for p in merged
        ]
        avg_merge_time = sum(merge_times_hours) / len(merge_times_hours)
    else:
        avg_merge_time = 0.0

    avg_cycles = sum(p.review_cycles for p in prs) / total

    return PRMetrics(
        total_prs=total,
        avg_merge_time_hours=round(avg_merge_time, 2),
        avg_review_cycles=round(avg_cycles, 2),
        merge_rate=round(merge_rate, 2),
    )
