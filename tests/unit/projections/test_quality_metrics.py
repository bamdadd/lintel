"""Tests for the QualityMetricsProjection (MET-5)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from lintel.contracts.events import (
    CommitPushed,
    PRCreated,
    TestRunCompleted,
    WorkItemCreated,
)
from lintel.contracts.types import ThreadRef
from lintel.infrastructure.projections.quality_metrics import QualityMetricsProjection


def _thread_ref() -> ThreadRef:
    return ThreadRef("W1", "C1", "t1")


def _now() -> datetime:
    return datetime.now(UTC)


class TestQualityMetricsProjectionHandledTypes:
    async def test_handles_expected_event_types(self) -> None:
        proj = QualityMetricsProjection()
        assert "TestRunCompleted" in proj.handled_event_types
        assert "CommitPushed" in proj.handled_event_types
        assert "WorkItemCreated" in proj.handled_event_types
        assert "PRCreated" in proj.handled_event_types

    async def test_does_not_handle_unrelated_events(self) -> None:
        proj = QualityMetricsProjection()
        assert "ThreadMessageReceived" not in proj.handled_event_types
        assert "WorkflowStarted" not in proj.handled_event_types


class TestCoverageDelta:
    async def test_records_coverage_from_test_run(self) -> None:
        proj = QualityMetricsProjection()
        await proj.project(
            TestRunCompleted(
                thread_ref=_thread_ref(),
                payload={
                    "project_id": "proj-1",
                    "commit_sha": "abc123",
                    "pr_id": "pr-10",
                    "coverage_before": 0.75,
                    "coverage_after": 0.82,
                },
            )
        )

        deltas = proj.get_coverage_deltas(project_id="proj-1", days=30)
        assert len(deltas) == 1
        assert deltas[0]["delta"] == 0.07
        assert deltas[0]["commit_sha"] == "abc123"
        assert deltas[0]["coverage_before"] == 0.75
        assert deltas[0]["coverage_after"] == 0.82

    async def test_filters_by_project_id(self) -> None:
        proj = QualityMetricsProjection()
        for pid in ("proj-1", "proj-2"):
            await proj.project(
                TestRunCompleted(
                    thread_ref=_thread_ref(),
                    payload={
                        "project_id": pid,
                        "commit_sha": "sha",
                        "coverage_before": 0.5,
                        "coverage_after": 0.6,
                    },
                )
            )

        assert len(proj.get_coverage_deltas(project_id="proj-1")) == 1
        # Empty project_id returns all
        assert len(proj.get_coverage_deltas(project_id="")) == 2

    async def test_filters_by_window(self) -> None:
        proj = QualityMetricsProjection()
        old_event = TestRunCompleted(
            thread_ref=_thread_ref(),
            occurred_at=_now() - timedelta(days=60),
            payload={
                "project_id": "p",
                "commit_sha": "old",
                "coverage_before": 0.5,
                "coverage_after": 0.6,
            },
        )
        recent_event = TestRunCompleted(
            thread_ref=_thread_ref(),
            payload={
                "project_id": "p",
                "commit_sha": "new",
                "coverage_before": 0.6,
                "coverage_after": 0.7,
            },
        )
        await proj.project(old_event)
        await proj.project(recent_event)

        assert len(proj.get_coverage_deltas(days=30)) == 1
        assert len(proj.get_coverage_deltas(days=90)) == 2


class TestDefectDensity:
    async def test_counts_bug_work_items(self) -> None:
        proj = QualityMetricsProjection()
        # Two bugs
        for _ in range(2):
            await proj.project(
                WorkItemCreated(
                    thread_ref=_thread_ref(),
                    payload={"project_id": "p1", "work_type": "BUG"},
                )
            )
        # One feature (should be ignored)
        await proj.project(
            WorkItemCreated(
                thread_ref=_thread_ref(),
                payload={"project_id": "p1", "work_type": "FEATURE"},
            )
        )
        # 100 lines of code changed
        await proj.project(
            CommitPushed(
                thread_ref=_thread_ref(),
                payload={"project_id": "p1", "commit_sha": "abc", "lines_changed": 100},
            )
        )

        density = proj.get_defect_density(project_id="p1")
        assert density["bug_count"] == 2
        assert density["lines_changed"] == 100
        assert density["density"] == 0.02  # 2/100

    async def test_zero_lines_yields_zero_density(self) -> None:
        proj = QualityMetricsProjection()
        await proj.project(
            WorkItemCreated(
                thread_ref=_thread_ref(),
                payload={"project_id": "p1", "work_type": "BUG"},
            )
        )
        density = proj.get_defect_density(project_id="p1")
        assert density["density"] == 0.0

    async def test_ignores_non_bug_work_items(self) -> None:
        proj = QualityMetricsProjection()
        await proj.project(
            WorkItemCreated(
                thread_ref=_thread_ref(),
                payload={"project_id": "p1", "work_type": "FEATURE"},
            )
        )
        density = proj.get_defect_density(project_id="p1")
        assert density["bug_count"] == 0

    async def test_rolling_window(self) -> None:
        proj = QualityMetricsProjection()
        # Old bug outside 30-day window
        await proj.project(
            WorkItemCreated(
                thread_ref=_thread_ref(),
                occurred_at=_now() - timedelta(days=45),
                payload={"project_id": "p1", "work_type": "BUG"},
            )
        )
        # Recent bug
        await proj.project(
            WorkItemCreated(
                thread_ref=_thread_ref(),
                payload={"project_id": "p1", "work_type": "BUG"},
            )
        )
        await proj.project(
            CommitPushed(
                thread_ref=_thread_ref(),
                payload={"project_id": "p1", "commit_sha": "x", "lines_changed": 50},
            )
        )

        d30 = proj.get_defect_density(project_id="p1", days=30)
        assert d30["bug_count"] == 1

        d60 = proj.get_defect_density(project_id="p1", days=60)
        assert d60["bug_count"] == 2


class TestReworkRatio:
    async def test_detects_rework_within_seven_days(self) -> None:
        proj = QualityMetricsProjection()
        merge_time = _now() - timedelta(days=3)

        # PR merged 3 days ago touching file_a.py
        await proj.project(
            PRCreated(
                thread_ref=_thread_ref(),
                occurred_at=merge_time,
                payload={"project_id": "p1", "pr_id": "pr-1", "files": ["file_a.py"]},
            )
        )
        # Commit now touching file_a.py again (rework)
        await proj.project(
            CommitPushed(
                thread_ref=_thread_ref(),
                payload={
                    "project_id": "p1",
                    "commit_sha": "rework1",
                    "lines_changed": 40,
                    "files": ["file_a.py"],
                },
            )
        )
        # Commit now touching file_b.py (not rework)
        await proj.project(
            CommitPushed(
                thread_ref=_thread_ref(),
                payload={
                    "project_id": "p1",
                    "commit_sha": "clean1",
                    "lines_changed": 60,
                    "files": ["file_b.py"],
                },
            )
        )

        result = proj.get_rework_ratio(project_id="p1")
        assert result["rework_loc"] == 40
        assert result["total_loc"] == 100
        assert result["ratio"] == 0.4

    async def test_no_rework_outside_seven_day_window(self) -> None:
        proj = QualityMetricsProjection()
        # PR merged 10 days ago
        await proj.project(
            PRCreated(
                thread_ref=_thread_ref(),
                occurred_at=_now() - timedelta(days=10),
                payload={"project_id": "p1", "pr_id": "pr-1", "files": ["file_a.py"]},
            )
        )
        # Commit now touching same file — outside 7-day window
        await proj.project(
            CommitPushed(
                thread_ref=_thread_ref(),
                payload={
                    "project_id": "p1",
                    "commit_sha": "c1",
                    "lines_changed": 50,
                    "files": ["file_a.py"],
                },
            )
        )

        result = proj.get_rework_ratio(project_id="p1")
        assert result["rework_loc"] == 0
        assert result["ratio"] == 0.0

    async def test_zero_commits_yields_zero_ratio(self) -> None:
        proj = QualityMetricsProjection()
        result = proj.get_rework_ratio(project_id="p1")
        assert result["ratio"] == 0.0
        assert result["total_loc"] == 0


class TestRebuild:
    async def test_rebuild_clears_and_replays(self) -> None:
        proj = QualityMetricsProjection()
        ref = _thread_ref()

        # First project some events
        await proj.project(
            TestRunCompleted(
                thread_ref=ref,
                payload={
                    "project_id": "p1",
                    "commit_sha": "a",
                    "coverage_before": 0.5,
                    "coverage_after": 0.6,
                },
            )
        )
        assert len(proj.get_coverage_deltas()) == 1

        # Rebuild with different events
        new_events = [
            TestRunCompleted(
                thread_ref=ref,
                payload={
                    "project_id": "p1",
                    "commit_sha": "b",
                    "coverage_before": 0.6,
                    "coverage_after": 0.7,
                },
            ),
            TestRunCompleted(
                thread_ref=ref,
                payload={
                    "project_id": "p1",
                    "commit_sha": "c",
                    "coverage_before": 0.7,
                    "coverage_after": 0.8,
                },
            ),
        ]
        await proj.rebuild(new_events)

        deltas = proj.get_coverage_deltas()
        assert len(deltas) == 2
        assert deltas[0]["commit_sha"] == "b"
        assert deltas[1]["commit_sha"] == "c"


class TestQualitySummary:
    async def test_get_quality_summary_returns_all_metrics(self) -> None:
        proj = QualityMetricsProjection()
        ref = _thread_ref()

        await proj.project(
            TestRunCompleted(
                thread_ref=ref,
                payload={
                    "project_id": "p1",
                    "commit_sha": "a",
                    "coverage_before": 0.7,
                    "coverage_after": 0.8,
                },
            )
        )
        await proj.project(
            WorkItemCreated(
                thread_ref=ref,
                payload={"project_id": "p1", "work_type": "BUG"},
            )
        )
        await proj.project(
            CommitPushed(
                thread_ref=ref,
                payload={
                    "project_id": "p1",
                    "commit_sha": "x",
                    "lines_changed": 200,
                    "files": ["main.py"],
                },
            )
        )

        summary = proj.get_quality_summary(project_id="p1", days=30)
        assert "coverage_deltas" in summary
        assert "defect_density" in summary
        assert "rework_ratio" in summary
        assert summary["window_days"] == 30
        assert len(summary["coverage_deltas"]) == 1
        assert summary["defect_density"]["bug_count"] == 1
