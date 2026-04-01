"""In-memory store for review scores."""

from __future__ import annotations

from typing import Any


class ReviewScoreStore:
    """In-memory store for review score records."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, data: dict[str, Any]) -> None:
        score_id = data["score_id"]
        self._data[score_id] = data

    async def get(self, score_id: str) -> dict[str, Any] | None:
        return self._data.get(score_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def get_trend_by_repo(
        self,
        repo_id: str,
        dimension: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return scores for a repo, optionally filtered by dimension."""
        results = [d for d in self._data.values() if d.get("repo_id") == repo_id]
        if dimension is not None:
            results = [d for d in results if d.get("dimension") == dimension]
        return sorted(results, key=lambda d: d.get("recorded_at", ""))

    async def get_trend_by_contributor(
        self,
        contributor_id: str,
        dimension: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return scores for a contributor, optionally filtered by dimension."""
        results = [d for d in self._data.values() if d.get("contributor_id") == contributor_id]
        if dimension is not None:
            results = [d for d in results if d.get("dimension") == dimension]
        return sorted(results, key=lambda d: d.get("recorded_at", ""))

    async def remove(self, score_id: str) -> bool:
        return self._data.pop(score_id, None) is not None
