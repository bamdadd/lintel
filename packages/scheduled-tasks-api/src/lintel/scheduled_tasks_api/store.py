"""In-memory scheduled task store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.scheduled_tasks_api.types import ScheduledTask


class InMemoryScheduledTaskStore:
    """Simple in-memory store for scheduled tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, ScheduledTask] = {}

    async def add(self, task: ScheduledTask) -> None:
        self._tasks[task.id] = task

    async def get(self, task_id: str) -> ScheduledTask | None:
        return self._tasks.get(task_id)

    async def list_all(self) -> list[ScheduledTask]:
        return list(self._tasks.values())

    async def list_by_project(self, project_id: str) -> list[ScheduledTask]:
        return [t for t in self._tasks.values() if t.project_id == project_id]

    async def update(self, task: ScheduledTask) -> None:
        self._tasks[task.id] = task

    async def remove(self, task_id: str) -> None:
        del self._tasks[task_id]
