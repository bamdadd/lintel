"""Tests for InMemoryAutomationStore."""

import pytest

from lintel.automations.store import InMemoryAutomationStore
from lintel.automations.types import AutomationDefinition, AutomationTriggerType


def _make_automation(
    automation_id: str = "a-1", project_id: str = "proj-1"
) -> AutomationDefinition:
    return AutomationDefinition(
        automation_id=automation_id,
        name="Test",
        project_id=project_id,
        workflow_definition_id="wf-1",
        trigger_type=AutomationTriggerType.CRON,
        trigger_config={"schedule": "0 2 * * *"},
    )


class TestInMemoryAutomationStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryAutomationStore()
        auto = _make_automation()
        await store.add(auto)
        result = await store.get("a-1")
        assert result is not None
        assert result.automation_id == "a-1"

    async def test_get_returns_none_for_missing(self) -> None:
        store = InMemoryAutomationStore()
        assert await store.get("nonexistent") is None

    async def test_list_all(self) -> None:
        store = InMemoryAutomationStore()
        await store.add(_make_automation("a-1"))
        await store.add(_make_automation("a-2"))
        result = await store.list_all()
        assert len(result) == 2

    async def test_list_all_filter_by_project(self) -> None:
        store = InMemoryAutomationStore()
        await store.add(_make_automation("a-1", project_id="proj-1"))
        await store.add(_make_automation("a-2", project_id="proj-2"))
        result = await store.list_all(project_id="proj-1")
        assert len(result) == 1
        assert result[0].automation_id == "a-1"

    async def test_update(self) -> None:
        store = InMemoryAutomationStore()
        await store.add(_make_automation("a-1"))
        updated = AutomationDefinition(
            automation_id="a-1",
            name="Updated",
            project_id="proj-1",
            workflow_definition_id="wf-1",
            trigger_type=AutomationTriggerType.CRON,
            trigger_config={"schedule": "0 3 * * *"},
        )
        await store.update(updated)
        result = await store.get("a-1")
        assert result is not None
        assert result.name == "Updated"

    async def test_update_nonexistent_raises(self) -> None:
        store = InMemoryAutomationStore()
        with pytest.raises(KeyError):
            await store.update(_make_automation("nonexistent"))

    async def test_remove(self) -> None:
        store = InMemoryAutomationStore()
        await store.add(_make_automation("a-1"))
        await store.remove("a-1")
        assert await store.get("a-1") is None

    async def test_remove_nonexistent_raises(self) -> None:
        store = InMemoryAutomationStore()
        with pytest.raises(KeyError):
            await store.remove("nonexistent")
