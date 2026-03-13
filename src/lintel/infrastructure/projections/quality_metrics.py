"""Quality metrics projection (MET-5).

Maintains in-memory aggregates for three quality signals:

* **Test Coverage Delta** — coverage_after - coverage_before per PR/commit,
  derived from ``TestRunCompleted`` events.
* **Defect Density** — COUNT(BUG work items) / lines_of_code_changed over
  rolling 30/60/90-day windows, from ``WorkItemCreated`` + ``CommitPushed``.
* **Rework Ratio** — SUM(rework_commit_LOC) / SUM(total_commit_LOC) where
  *rework* means touching the same files within 7 days of merge, derived from
  ``CommitPushed`` and ``PRCreated`` events.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


@dataclass
class CoverageRecord:
    """Coverage snapshot from a single test run."""

    project_id: str
    commit_sha: str
    pr_id: str
    coverage_before: float
    coverage_after: float
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def delta(self) -> float:
        return self.coverage_after - self.coverage_before


@dataclass
class DefectRecord:
    """A bug work item recorded for defect-density calculation."""

    project_id: str
    work_item_id: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class CommitRecord:
    """Lines-of-code data from a single commit."""

    project_id: str
    commit_sha: str
    lines_changed: int
    files: list[str]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MergeRecord:
    """Tracks when a PR was created/merged and which files it touched."""

    project_id: str
    pr_id: str
    files: list[str]
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))


_REWORK_WINDOW = timedelta(days=7)


class QualityMetricsProjection:
    """Builds read-model aggregates for MET-5 quality metrics."""

    HANDLED_TYPES: frozenset[str] = frozenset(
        {
            "TestRunCompleted",
            "CommitPushed",
            "WorkItemCreated",
            "PRCreated",
        }
    )

    def __init__(self) -> None:
        self._coverage_records: list[CoverageRecord] = []
        self._defect_records: list[DefectRecord] = []
        self._commit_records: list[CommitRecord] = []
        self._merge_records: list[MergeRecord] = []

    # -- Projection protocol ------------------------------------------------

    @property
    def handled_event_types(self) -> set[str]:
        return set(self.HANDLED_TYPES)

    async def project(self, event: EventEnvelope) -> None:
        handler = _HANDLERS.get(event.event_type)
        if handler:
            handler(self, event)

    async def rebuild(self, events: list[EventEnvelope]) -> None:
        self._coverage_records.clear()
        self._defect_records.clear()
        self._commit_records.clear()
        self._merge_records.clear()
        for event in events:
            if event.event_type in self.handled_event_types:
                await self.project(event)

    # -- Event handlers -----------------------------------------------------

    def _on_test_run_completed(self, event: EventEnvelope) -> None:
        payload = event.payload
        self._coverage_records.append(
            CoverageRecord(
                project_id=payload.get("project_id", ""),
                commit_sha=payload.get("commit_sha", ""),
                pr_id=payload.get("pr_id", ""),
                coverage_before=float(payload.get("coverage_before", 0.0)),
                coverage_after=float(payload.get("coverage_after", 0.0)),
                occurred_at=event.occurred_at,
            )
        )

    def _on_commit_pushed(self, event: EventEnvelope) -> None:
        payload = event.payload
        files_raw = payload.get("files", [])
        files = list(files_raw) if isinstance(files_raw, (list, tuple)) else []
        self._commit_records.append(
            CommitRecord(
                project_id=payload.get("project_id", ""),
                commit_sha=payload.get("commit_sha", ""),
                lines_changed=int(payload.get("lines_changed", 0)),
                files=files,
                occurred_at=event.occurred_at,
            )
        )

    def _on_work_item_created(self, event: EventEnvelope) -> None:
        payload = event.payload
        work_type = payload.get("work_type", "").upper()
        if work_type != "BUG":
            return
        self._defect_records.append(
            DefectRecord(
                project_id=payload.get("project_id", ""),
                work_item_id=payload.get("work_item_id", str(event.event_id)),
                occurred_at=event.occurred_at,
            )
        )

    def _on_pr_created(self, event: EventEnvelope) -> None:
        payload = event.payload
        files_raw = payload.get("files", [])
        files = list(files_raw) if isinstance(files_raw, (list, tuple)) else []
        self._merge_records.append(
            MergeRecord(
                project_id=payload.get("project_id", ""),
                pr_id=payload.get("pr_id", str(event.event_id)),
                files=files,
                occurred_at=event.occurred_at,
            )
        )

    # -- Query helpers ------------------------------------------------------

    def get_coverage_deltas(
        self,
        *,
        project_id: str = "",
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Return per-commit coverage deltas within the window."""
        cutoff = datetime.now(UTC) - timedelta(days=days)
        results: list[dict[str, Any]] = []
        for rec in self._coverage_records:
            if rec.occurred_at < cutoff:
                continue
            if project_id and rec.project_id != project_id:
                continue
            results.append(
                {
                    "project_id": rec.project_id,
                    "commit_sha": rec.commit_sha,
                    "pr_id": rec.pr_id,
                    "coverage_before": rec.coverage_before,
                    "coverage_after": rec.coverage_after,
                    "delta": round(rec.delta, 4),
                    "occurred_at": rec.occurred_at.isoformat(),
                }
            )
        return results

    def get_defect_density(
        self,
        *,
        project_id: str = "",
        days: int = 30,
    ) -> dict[str, Any]:
        """COUNT(BUG) / lines_changed over the rolling window."""
        cutoff = datetime.now(UTC) - timedelta(days=days)

        bug_count = sum(
            1
            for d in self._defect_records
            if d.occurred_at >= cutoff and (not project_id or d.project_id == project_id)
        )
        total_lines = sum(
            c.lines_changed
            for c in self._commit_records
            if c.occurred_at >= cutoff and (not project_id or c.project_id == project_id)
        )
        density = (bug_count / total_lines) if total_lines > 0 else 0.0
        return {
            "bug_count": bug_count,
            "lines_changed": total_lines,
            "density": round(density, 6),
            "window_days": days,
        }

    def get_rework_ratio(
        self,
        *,
        project_id: str = "",
        days: int = 30,
    ) -> dict[str, Any]:
        """SUM(rework_LOC) / SUM(total_LOC).

        A commit is *rework* if it touches any file that was also part of a
        PR/merge within the preceding 7 days.
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        total_loc = 0
        rework_loc = 0
        for commit in self._commit_records:
            if commit.occurred_at < cutoff:
                continue
            if project_id and commit.project_id != project_id:
                continue
            total_loc += commit.lines_changed

            # Check if any of the commit's files overlap with a recent merge
            merge_cutoff = commit.occurred_at - _REWORK_WINDOW
            is_rework = False
            for merge in self._merge_records:
                if merge.occurred_at < merge_cutoff or merge.occurred_at > commit.occurred_at:
                    continue
                if project_id and merge.project_id != project_id:
                    continue
                if set(commit.files) & set(merge.files):
                    is_rework = True
                    break
            if is_rework:
                rework_loc += commit.lines_changed

        ratio = (rework_loc / total_loc) if total_loc > 0 else 0.0
        return {
            "rework_loc": rework_loc,
            "total_loc": total_loc,
            "ratio": round(ratio, 4),
            "window_days": days,
        }

    def get_quality_summary(
        self,
        *,
        project_id: str = "",
        days: int = 30,
    ) -> dict[str, Any]:
        """Return a combined quality metrics summary."""
        return {
            "coverage_deltas": self.get_coverage_deltas(project_id=project_id, days=days),
            "defect_density": self.get_defect_density(project_id=project_id, days=days),
            "rework_ratio": self.get_rework_ratio(project_id=project_id, days=days),
            "window_days": days,
        }


# Dispatch table avoids long if/elif chains
_HANDLERS: dict[str, Any] = {
    "TestRunCompleted": QualityMetricsProjection._on_test_run_completed,
    "CommitPushed": QualityMetricsProjection._on_commit_pushed,
    "WorkItemCreated": QualityMetricsProjection._on_work_item_created,
    "PRCreated": QualityMetricsProjection._on_pr_created,
}
