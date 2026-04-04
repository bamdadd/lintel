"""Digest generation logic — summarises work items and pipelines for a period."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol
from uuid import uuid4

from lintel.digest_api.types import Digest


class WorkItemReader(Protocol):
    """Read-only access to work items (duck-typed)."""

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]: ...


class PipelineReader(Protocol):
    """Read-only access to pipeline runs (duck-typed)."""

    async def list_all(self, *, project_id: str | None = None) -> list[dict[str, Any]]: ...


class DigestGenerator:
    """Builds a weekly progress digest from work-item and pipeline data."""

    def __init__(
        self,
        work_item_store: WorkItemReader,
        pipeline_store: PipelineReader,
    ) -> None:
        self._work_items = work_item_store
        self._pipelines = pipeline_store

    async def generate(
        self,
        *,
        project_id: str,
        team_id: str,
        period_start: datetime,
        period_end: datetime,
    ) -> Digest:
        work_items = await self._work_items.list_all(project_id=project_id)
        pipelines = await self._pipelines.list_all(project_id=project_id)

        # Filter work items updated within the period
        period_items = _filter_by_period(work_items, period_start, period_end)
        period_pipelines = _filter_by_period(pipelines, period_start, period_end)

        done = [wi for wi in period_items if _status(wi) in ("done", "completed", "merged")]
        in_progress = [wi for wi in period_items if _status(wi) in ("in_progress", "open")]

        succeeded = [p for p in period_pipelines if _status(p) in ("completed", "succeeded")]
        failed = [p for p in period_pipelines if _status(p) == "failed"]

        metrics: dict[str, object] = {
            "work_items_completed": len(done),
            "work_items_in_progress": len(in_progress),
            "pipelines_succeeded": len(succeeded),
            "pipelines_failed": len(failed),
            "total_work_items": len(period_items),
            "total_pipelines": len(period_pipelines),
        }

        highlights: list[str] = []
        if done:
            highlights.append(f"{len(done)} work item(s) completed")
        if succeeded:
            highlights.append(f"{len(succeeded)} pipeline(s) succeeded")
        if failed:
            highlights.append(f"{len(failed)} pipeline(s) failed")
        if in_progress:
            highlights.append(f"{len(in_progress)} work item(s) still in progress")

        summary = _build_summary(done, in_progress, succeeded, failed)

        return Digest(
            id=str(uuid4()),
            project_id=project_id,
            team_id=team_id,
            period_start=period_start,
            period_end=period_end,
            summary=summary,
            metrics=metrics,
            highlights=highlights,
        )


def _status(item: dict[str, Any]) -> str:
    return str(item.get("status", "")).lower()


def _filter_by_period(
    items: list[dict[str, Any]],
    start: datetime,
    end: datetime,
) -> list[dict[str, Any]]:
    """Filter items that fall within the period based on updated_at or created_at."""
    result: list[dict[str, Any]] = []
    for item in items:
        ts_raw = item.get("updated_at") or item.get("created_at")
        if ts_raw is None:
            continue
        ts = _parse_dt(ts_raw)
        if ts is None:
            continue
        if start <= ts <= end:
            result.append(item)
    return result


def _parse_dt(value: Any) -> datetime | None:  # noqa: ANN401
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _build_summary(
    done: list[dict[str, Any]],
    in_progress: list[dict[str, Any]],
    succeeded: list[dict[str, Any]],
    failed: list[dict[str, Any]],
) -> str:
    parts: list[str] = []
    parts.append(f"Completed {len(done)} work item(s).")
    parts.append(f"{len(succeeded)} pipeline(s) succeeded, {len(failed)} failed.")
    if in_progress:
        parts.append(f"{len(in_progress)} work item(s) still in progress.")
    return " ".join(parts)
