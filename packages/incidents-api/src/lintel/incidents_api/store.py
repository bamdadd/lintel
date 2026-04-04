"""In-memory store for incidents."""

from __future__ import annotations

from typing import Any


class InMemoryIncidentStore:
    """Simple in-memory store for incidents."""

    def __init__(self) -> None:
        self._incidents: dict[str, dict[str, Any]] = {}

    async def add(self, incident_id: str, data: dict[str, Any]) -> None:
        self._incidents[incident_id] = data

    async def get(self, incident_id: str) -> dict[str, Any] | None:
        return self._incidents.get(incident_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items = list(self._incidents.values())
        if project_id is not None:
            items = [i for i in items if i.get("project_id") == project_id]
        return items
