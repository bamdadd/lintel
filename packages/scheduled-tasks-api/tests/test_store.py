"""Tests for InMemoryScheduledTaskStore."""

import pytest

from lintel.scheduled_tasks_api.store import InMemoryScheduledTaskStore
from lintel.scheduled_tasks_api.types import ScheduledTask, TaskType


class TestInMemoryScheduledTaskStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryScheduledTaskStore()
        task = ScheduledTask(
            id="st-1",
            project_id="proj-1",
            name="Nightly Update",
            cron_expression="0 0 * * *",
            task_type=TaskType.DEPENDENCY_UPDATE,
        )
        await store.add(task)
        result = await store.get("st-1")
        assert result is not None
        assert result.name == "Nightly Update"

    async def test_get_returns_none_when_not_found(self) -> None:
        store = InMemoryScheduledTaskStore()
        result = await store.get("nonexistent")
        assert result is None

    async def test_list_all(self) -> None:
        store = InMemoryScheduledTaskStore()
        task1 = ScheduledTask(
            id="st-1",
            project_id="proj-1",
            name="Task 1",
            cron_expression="0 0 * * *",
            task_type=TaskType.COVERAGE_SWEEP,
        )
        task2 = ScheduledTask(
            id="st-2",
            project_id="proj-2",
            name="Task 2",
            cron_expression="0 0 * * 0",
            task_type=TaskType.SECURITY_SCAN,
        )
        await store.add(task1)
        await store.add(task2)
        result = await store.list_all()
        assert len(result) == 2

    async def test_list_by_project(self) -> None:
        store = InMemoryScheduledTaskStore()
        task1 = ScheduledTask(
            id="st-1",
            project_id="proj-1",
            name="Task 1",
            cron_expression="0 0 * * *",
            task_type=TaskType.CUSTOM,
        )
        task2 = ScheduledTask(
            id="st-2",
            project_id="proj-2",
            name="Task 2",
            cron_expression="0 0 * * *",
            task_type=TaskType.CUSTOM,
        )
        await store.add(task1)
        await store.add(task2)
        result = await store.list_by_project("proj-1")
        assert len(result) == 1
        assert result[0].project_id == "proj-1"

    async def test_update(self) -> None:
        store = InMemoryScheduledTaskStore()
        task = ScheduledTask(
            id="st-1",
            project_id="proj-1",
            name="Original",
            cron_expression="0 0 * * *",
            task_type=TaskType.DEPENDENCY_UPDATE,
        )
        await store.add(task)
        updated = ScheduledTask(
            id="st-1",
            project_id="proj-1",
            name="Updated",
            cron_expression="0 0 * * *",
            task_type=TaskType.DEPENDENCY_UPDATE,
        )
        await store.update(updated)
        result = await store.get("st-1")
        assert result is not None
        assert result.name == "Updated"

    async def test_remove(self) -> None:
        store = InMemoryScheduledTaskStore()
        task = ScheduledTask(
            id="st-1",
            project_id="proj-1",
            name="To Remove",
            cron_expression="0 0 * * *",
            task_type=TaskType.SECURITY_SCAN,
        )
        await store.add(task)
        await store.remove("st-1")
        assert await store.get("st-1") is None

    async def test_remove_nonexistent_raises(self) -> None:
        store = InMemoryScheduledTaskStore()
        with pytest.raises(KeyError):
            await store.remove("nonexistent")
