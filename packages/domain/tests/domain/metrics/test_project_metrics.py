"""Tests for REQ-030: Project Commit & PR Metrics Dashboard."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lintel.domain.metrics.project_metrics import (
    CommitMetrics,
    CommitRecord,
    PRMetrics,
    ProjectMetricsCollector,
    ProjectMetricsDashboard,
    PRRecord,
)

_NOW = datetime(2026, 4, 1, 12, 0, 0, tzinfo=UTC)


def _commit(
    sha: str = "abc",
    author: str = "alice",
    days_ago: int = 1,
    added: int = 10,
    removed: int = 5,
) -> CommitRecord:
    return CommitRecord(
        sha=sha,
        author=author,
        committed_at=_NOW - timedelta(days=days_ago),
        lines_added=added,
        lines_removed=removed,
    )


def _pr(
    pr_id: str = "pr-1",
    author: str = "alice",
    days_ago: int = 5,
    merged_hours_later: float | None = 24.0,
    review_cycles: int = 2,
) -> PRRecord:
    created = _NOW - timedelta(days=days_ago)
    merged = (
        created + timedelta(hours=merged_hours_later) if merged_hours_later is not None else None
    )
    return PRRecord(
        pr_id=pr_id,
        author=author,
        created_at=created,
        merged_at=merged,
        review_cycles=review_cycles,
    )


# ---------------------------------------------------------------------------
# Frozen dataclass tests
# ---------------------------------------------------------------------------


class TestCommitMetrics:
    def test_frozen(self) -> None:
        m = CommitMetrics(
            total_commits=1, commits_per_day=0.5, avg_lines_changed=10.0, top_contributors=("a",)
        )
        assert m.total_commits == 1

    def test_equality(self) -> None:
        a = CommitMetrics(
            total_commits=1, commits_per_day=0.5, avg_lines_changed=10.0, top_contributors=()
        )
        b = CommitMetrics(
            total_commits=1, commits_per_day=0.5, avg_lines_changed=10.0, top_contributors=()
        )
        assert a == b


class TestPRMetrics:
    def test_frozen(self) -> None:
        m = PRMetrics(total_prs=3, avg_merge_time_hours=12.0, avg_review_cycles=1.5, merge_rate=0.8)
        assert m.merge_rate == 0.8

    def test_equality(self) -> None:
        a = PRMetrics(total_prs=0, avg_merge_time_hours=0.0, avg_review_cycles=0.0, merge_rate=0.0)
        b = PRMetrics(total_prs=0, avg_merge_time_hours=0.0, avg_review_cycles=0.0, merge_rate=0.0)
        assert a == b


class TestProjectMetricsDashboard:
    def test_fields(self) -> None:
        cm = CommitMetrics(
            total_commits=0, commits_per_day=0.0, avg_lines_changed=0.0, top_contributors=()
        )
        pm = PRMetrics(total_prs=0, avg_merge_time_hours=0.0, avg_review_cycles=0.0, merge_rate=0.0)
        d = ProjectMetricsDashboard(
            project_id="p1",
            window_start=_NOW - timedelta(days=30),
            window_end=_NOW,
            commit_metrics=cm,
            pr_metrics=pm,
        )
        assert d.project_id == "p1"
        assert d.commit_metrics.total_commits == 0


# ---------------------------------------------------------------------------
# Collector — empty inputs
# ---------------------------------------------------------------------------


class TestCollectorEmpty:
    def test_no_data_returns_zeros(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        d = c.compute(now=_NOW)
        assert d.commit_metrics.total_commits == 0
        assert d.pr_metrics.total_prs == 0
        assert d.pr_metrics.merge_rate == 0.0

    def test_window_boundaries(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        d = c.compute(window_days=7, now=_NOW)
        assert d.window_start == _NOW - timedelta(days=7)
        assert d.window_end == _NOW


# ---------------------------------------------------------------------------
# Collector — commit metrics
# ---------------------------------------------------------------------------


class TestCollectorCommitMetrics:
    def test_total_commits(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_commits([_commit(sha="1"), _commit(sha="2"), _commit(sha="3")])
        d = c.compute(window_days=30, now=_NOW)
        assert d.commit_metrics.total_commits == 3

    def test_commits_per_day(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_commits([_commit(sha=str(i)) for i in range(10)])
        d = c.compute(window_days=10, now=_NOW)
        assert d.commit_metrics.commits_per_day == 1.0

    def test_avg_lines_changed(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_commits(
            [
                _commit(sha="1", added=20, removed=10),
                _commit(sha="2", added=30, removed=0),
            ]
        )
        d = c.compute(window_days=30, now=_NOW)
        # (30 + 30) / 2 = 30
        assert d.commit_metrics.avg_lines_changed == 30.0

    def test_top_contributors_ordering(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_commits(
            [
                _commit(sha="1", author="bob"),
                _commit(sha="2", author="alice"),
                _commit(sha="3", author="alice"),
                _commit(sha="4", author="alice"),
                _commit(sha="5", author="bob"),
            ]
        )
        d = c.compute(window_days=30, now=_NOW)
        assert d.commit_metrics.top_contributors[0] == "alice"
        assert d.commit_metrics.top_contributors[1] == "bob"

    def test_top_contributors_limit(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_commits([_commit(sha=str(i), author=f"dev-{i}") for i in range(10)])
        d = c.compute(window_days=30, now=_NOW)
        assert len(d.commit_metrics.top_contributors) == 5

    def test_commits_outside_window_excluded(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_commits(
            [
                _commit(sha="old", days_ago=60),
                _commit(sha="new", days_ago=1),
            ]
        )
        d = c.compute(window_days=30, now=_NOW)
        assert d.commit_metrics.total_commits == 1

    def test_record_commit_single(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.record_commit(_commit(sha="single"))
        d = c.compute(window_days=30, now=_NOW)
        assert d.commit_metrics.total_commits == 1


# ---------------------------------------------------------------------------
# Collector — PR metrics
# ---------------------------------------------------------------------------


class TestCollectorPRMetrics:
    def test_total_prs(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_prs([_pr(pr_id="1"), _pr(pr_id="2")])
        d = c.compute(window_days=30, now=_NOW)
        assert d.pr_metrics.total_prs == 2

    def test_merge_rate(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_prs(
            [
                _pr(pr_id="1", merged_hours_later=10.0),
                _pr(pr_id="2", merged_hours_later=None),
            ]
        )
        d = c.compute(window_days=30, now=_NOW)
        assert d.pr_metrics.merge_rate == 0.5

    def test_avg_merge_time(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_prs(
            [
                _pr(pr_id="1", merged_hours_later=12.0),
                _pr(pr_id="2", merged_hours_later=36.0),
            ]
        )
        d = c.compute(window_days=30, now=_NOW)
        assert d.pr_metrics.avg_merge_time_hours == 24.0

    def test_avg_review_cycles(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_prs(
            [
                _pr(pr_id="1", review_cycles=1),
                _pr(pr_id="2", review_cycles=3),
            ]
        )
        d = c.compute(window_days=30, now=_NOW)
        assert d.pr_metrics.avg_review_cycles == 2.0

    def test_no_merged_prs(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_prs([_pr(pr_id="1", merged_hours_later=None)])
        d = c.compute(window_days=30, now=_NOW)
        assert d.pr_metrics.avg_merge_time_hours == 0.0
        assert d.pr_metrics.merge_rate == 0.0

    def test_prs_outside_window_excluded(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.ingest_prs(
            [
                _pr(pr_id="old", days_ago=60),
                _pr(pr_id="new", days_ago=2),
            ]
        )
        d = c.compute(window_days=30, now=_NOW)
        assert d.pr_metrics.total_prs == 1

    def test_record_pr_single(self) -> None:
        c = ProjectMetricsCollector(project_id="p1")
        c.record_pr(_pr(pr_id="single"))
        d = c.compute(window_days=30, now=_NOW)
        assert d.pr_metrics.total_prs == 1
