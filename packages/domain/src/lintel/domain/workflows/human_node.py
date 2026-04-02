"""Human-in-the-loop workflow node domain model.

Provides a task registry that tracks human tasks within workflow runs.
Tasks can be created, assigned, completed, and expired.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class HumanTaskStatus(StrEnum):
    """Lifecycle status of a human task."""

    PENDING = "pending"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class HumanTask:
    """A task requiring human action within a workflow."""

    task_id: str
    workflow_run_id: str
    stage_id: str
    assignee_email: str | None
    title: str
    description: str = ""
    status: HumanTaskStatus = HumanTaskStatus.PENDING
    response: dict[str, Any] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    expires_at: datetime | None = None


class HumanTaskRegistry:
    """In-memory registry for human tasks within workflows."""

    def __init__(self) -> None:
        self._tasks: dict[str, HumanTask] = {}

    def create_task(
        self,
        *,
        workflow_run_id: str,
        stage_id: str,
        title: str,
        description: str = "",
        assignee_email: str | None = None,
        expires_at: datetime | None = None,
    ) -> HumanTask:
        """Create a new human task and register it."""
        task = HumanTask(
            task_id=str(uuid4()),
            workflow_run_id=workflow_run_id,
            stage_id=stage_id,
            assignee_email=assignee_email,
            title=title,
            description=description,
            expires_at=expires_at,
        )
        self._tasks[task.task_id] = task
        return task

    def assign(self, task_id: str, assignee_email: str) -> HumanTask:
        """Assign a pending task to a human."""
        task = self._get_or_raise(task_id)
        if task.status != HumanTaskStatus.PENDING:
            msg = f"Cannot assign task in status {task.status}"
            raise ValueError(msg)
        updated = replace(task, assignee_email=assignee_email, status=HumanTaskStatus.ASSIGNED)
        self._tasks[task_id] = updated
        return updated

    def complete(self, task_id: str, response: dict[str, Any]) -> HumanTask:
        """Complete a task with a human response."""
        task = self._get_or_raise(task_id)
        if task.status not in {HumanTaskStatus.PENDING, HumanTaskStatus.ASSIGNED}:
            msg = f"Cannot complete task in status {task.status}"
            raise ValueError(msg)
        updated = replace(
            task,
            status=HumanTaskStatus.COMPLETED,
            response=response,
            completed_at=datetime.now(UTC),
        )
        self._tasks[task_id] = updated
        return updated

    def get_pending(self, assignee_email: str) -> list[HumanTask]:
        """Get all pending/assigned tasks for an assignee."""
        return [
            t
            for t in self._tasks.values()
            if t.assignee_email == assignee_email
            and t.status in {HumanTaskStatus.PENDING, HumanTaskStatus.ASSIGNED}
        ]

    def get_task(self, task_id: str) -> HumanTask | None:
        """Get a task by ID, or None if not found."""
        return self._tasks.get(task_id)

    def expire_overdue(self, *, now: datetime | None = None) -> list[HumanTask]:
        """Expire all overdue tasks. Returns the list of newly expired tasks."""
        now = now or datetime.now(UTC)
        expired: list[HumanTask] = []
        for task_id, task in self._tasks.items():
            if (
                task.status in {HumanTaskStatus.PENDING, HumanTaskStatus.ASSIGNED}
                and task.expires_at is not None
                and task.expires_at <= now
            ):
                updated = replace(task, status=HumanTaskStatus.EXPIRED)
                self._tasks[task_id] = updated
                expired.append(updated)
        return expired

    def cancel(self, task_id: str) -> HumanTask:
        """Cancel a pending or assigned task."""
        task = self._get_or_raise(task_id)
        if task.status not in {HumanTaskStatus.PENDING, HumanTaskStatus.ASSIGNED}:
            msg = f"Cannot cancel task in status {task.status}"
            raise ValueError(msg)
        updated = replace(task, status=HumanTaskStatus.CANCELLED)
        self._tasks[task_id] = updated
        return updated

    def _get_or_raise(self, task_id: str) -> HumanTask:
        task = self._tasks.get(task_id)
        if task is None:
            msg = f"Task {task_id} not found"
            raise KeyError(msg)
        return task
