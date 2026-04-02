"""Tests for human-in-the-loop workflow node domain model."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lintel.domain.workflows.human_node import (
    HumanTask,
    HumanTaskRegistry,
    HumanTaskStatus,
)


@pytest.fixture
def registry() -> HumanTaskRegistry:
    return HumanTaskRegistry()


class TestHumanTaskStatus:
    def test_values(self) -> None:
        assert HumanTaskStatus.PENDING == "pending"
        assert HumanTaskStatus.ASSIGNED == "assigned"
        assert HumanTaskStatus.COMPLETED == "completed"
        assert HumanTaskStatus.EXPIRED == "expired"
        assert HumanTaskStatus.CANCELLED == "cancelled"


class TestHumanTask:
    def test_frozen(self) -> None:
        task = HumanTask(
            task_id="t1",
            workflow_run_id="w1",
            stage_id="s1",
            assignee_email=None,
            title="Review PR",
        )
        with pytest.raises(AttributeError):
            task.title = "changed"  # type: ignore[misc]

    def test_defaults(self) -> None:
        task = HumanTask(
            task_id="t1",
            workflow_run_id="w1",
            stage_id="s1",
            assignee_email=None,
            title="Do thing",
        )
        assert task.status == HumanTaskStatus.PENDING
        assert task.response is None
        assert task.completed_at is None
        assert task.expires_at is None
        assert task.description == ""


class TestHumanTaskRegistry:
    def test_create_task(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(
            workflow_run_id="w1",
            stage_id="s1",
            title="Review code",
            assignee_email="dev@example.com",
        )
        assert task.status == HumanTaskStatus.PENDING
        assert task.workflow_run_id == "w1"
        assert task.assignee_email == "dev@example.com"
        assert registry.get_task(task.task_id) == task

    def test_assign(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(workflow_run_id="w1", stage_id="s1", title="Review")
        assigned = registry.assign(task.task_id, "dev@example.com")
        assert assigned.status == HumanTaskStatus.ASSIGNED
        assert assigned.assignee_email == "dev@example.com"

    def test_assign_non_pending_raises(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(workflow_run_id="w1", stage_id="s1", title="Review")
        registry.complete(task.task_id, {"approved": True})
        with pytest.raises(ValueError, match="Cannot assign"):
            registry.assign(task.task_id, "dev@example.com")

    def test_complete(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(workflow_run_id="w1", stage_id="s1", title="Review")
        completed = registry.complete(task.task_id, {"approved": True})
        assert completed.status == HumanTaskStatus.COMPLETED
        assert completed.response == {"approved": True}
        assert completed.completed_at is not None

    def test_complete_assigned_task(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(workflow_run_id="w1", stage_id="s1", title="Review")
        registry.assign(task.task_id, "dev@example.com")
        completed = registry.complete(task.task_id, {"ok": True})
        assert completed.status == HumanTaskStatus.COMPLETED

    def test_complete_already_completed_raises(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(workflow_run_id="w1", stage_id="s1", title="Review")
        registry.complete(task.task_id, {"ok": True})
        with pytest.raises(ValueError, match="Cannot complete"):
            registry.complete(task.task_id, {"ok": False})

    def test_get_pending(self, registry: HumanTaskRegistry) -> None:
        registry.create_task(
            workflow_run_id="w1",
            stage_id="s1",
            title="Task 1",
            assignee_email="a@b.com",
        )
        t2 = registry.create_task(
            workflow_run_id="w1",
            stage_id="s2",
            title="Task 2",
            assignee_email="a@b.com",
        )
        registry.complete(t2.task_id, {"done": True})
        registry.create_task(
            workflow_run_id="w1",
            stage_id="s3",
            title="Task 3",
            assignee_email="other@b.com",
        )
        pending = registry.get_pending("a@b.com")
        assert len(pending) == 1
        assert pending[0].title == "Task 1"

    def test_get_task_not_found(self, registry: HumanTaskRegistry) -> None:
        assert registry.get_task("nonexistent") is None

    def test_expire_overdue(self, registry: HumanTaskRegistry) -> None:
        now = datetime.now(UTC)
        registry.create_task(
            workflow_run_id="w1",
            stage_id="s1",
            title="Overdue",
            expires_at=now - timedelta(hours=1),
        )
        registry.create_task(
            workflow_run_id="w1",
            stage_id="s2",
            title="Not yet",
            expires_at=now + timedelta(hours=1),
        )
        registry.create_task(
            workflow_run_id="w1",
            stage_id="s3",
            title="No expiry",
        )
        expired = registry.expire_overdue(now=now)
        assert len(expired) == 1
        assert expired[0].title == "Overdue"
        assert expired[0].status == HumanTaskStatus.EXPIRED

    def test_cancel(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(workflow_run_id="w1", stage_id="s1", title="Cancel me")
        cancelled = registry.cancel(task.task_id)
        assert cancelled.status == HumanTaskStatus.CANCELLED

    def test_cancel_completed_raises(self, registry: HumanTaskRegistry) -> None:
        task = registry.create_task(workflow_run_id="w1", stage_id="s1", title="Done")
        registry.complete(task.task_id, {"ok": True})
        with pytest.raises(ValueError, match="Cannot cancel"):
            registry.cancel(task.task_id)

    def test_unknown_task_raises_key_error(self, registry: HumanTaskRegistry) -> None:
        with pytest.raises(KeyError, match="not found"):
            registry.assign("no-such-id", "a@b.com")
