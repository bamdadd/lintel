"""In-memory store for review reports."""

from __future__ import annotations

from typing import Any


class ReviewReportStore:
    """In-memory store for review report entities."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, data: dict[str, Any]) -> None:
        report_id = data["report_id"]
        self._data[report_id] = data

    async def get(self, report_id: str) -> dict[str, Any] | None:
        return self._data.get(report_id)

    async def list_by_repo(self, repo_id: str) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if d.get("repo_id") == repo_id]

    async def list_by_pipeline_run(self, pipeline_run_id: str) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if d.get("pipeline_run_id") == pipeline_run_id]

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def remove(self, report_id: str) -> bool:
        return self._data.pop(report_id, None) is not None
