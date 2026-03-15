"""In-memory project store."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.domain.types import Project
from lintel.persistence.data_models import ProjectData


class ProjectStore:
    """In-memory project store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, project: Project) -> None:
        data = asdict(project)
        # Convert tuples to lists for JSON compat
        for key in ("repo_ids", "credential_ids"):
            if isinstance(data.get(key), tuple):
                data[key] = list(data[key])
        validated = ProjectData.model_validate(data)
        self._data[project.project_id] = validated.model_dump()

    async def get(self, project_id: str) -> dict[str, Any] | None:
        return self._data.get(project_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def update(self, project_id: str, data: dict[str, Any]) -> None:
        # Convert tuples to lists before validation
        for key in ("repo_ids", "credential_ids"):
            if isinstance(data.get(key), tuple):
                data[key] = list(data[key])
        validated = ProjectData.model_validate(data)
        self._data[project_id] = validated.model_dump()

    async def remove(self, project_id: str) -> None:
        self._data.pop(project_id, None)
