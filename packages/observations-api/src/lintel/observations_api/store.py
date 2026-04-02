"""In-memory observation store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any


class ObservationStore:
    """In-memory store for observations."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _to_dict(entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(entity)
        for k, v in data.items():
            if isinstance(v, tuple | frozenset):
                data[k] = list(v)
        return data

    async def add(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = self._to_dict(entity)
        self._data[data["observation_id"]] = data
        return data

    async def get(self, observation_id: str) -> dict[str, Any] | None:
        return self._data.get(observation_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def list_by_run(self, run_id: str) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if d.get("run_id") == run_id]

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if d.get("project_id") == project_id]

    async def list_unsynthesized(self) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if not d.get("synthesized_at")]

    async def mark_synthesized(
        self,
        observation_ids: list[str],
        synthesized_at: str,
    ) -> int:
        """Batch-update synthesized_at for given observation IDs. Returns count updated."""
        count = 0
        for oid in observation_ids:
            if oid in self._data:
                self._data[oid]["synthesized_at"] = synthesized_at
                count += 1
        return count

    async def remove(self, observation_id: str) -> bool:
        return self._data.pop(observation_id, None) is not None
