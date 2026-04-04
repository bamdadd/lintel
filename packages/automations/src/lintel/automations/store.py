"""In-memory automation store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.automations.types import AutomationDefinition


class InMemoryAutomationStore:
    """Simple in-memory store for automations."""

    def __init__(self) -> None:
        self._automations: dict[str, AutomationDefinition] = {}

    async def add(self, automation: AutomationDefinition) -> None:
        self._automations[automation.automation_id] = automation

    async def get(self, automation_id: str) -> AutomationDefinition | None:
        return self._automations.get(automation_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[AutomationDefinition]:
        items = list(self._automations.values())
        if project_id is not None:
            items = [a for a in items if a.project_id == project_id]
        return items

    async def update(self, automation: AutomationDefinition) -> None:
        if automation.automation_id not in self._automations:
            msg = f"Automation {automation.automation_id} not found"
            raise KeyError(msg)
        self._automations[automation.automation_id] = automation

    async def remove(self, automation_id: str) -> None:
        if automation_id not in self._automations:
            msg = f"Automation {automation_id} not found"
            raise KeyError(msg)
        del self._automations[automation_id]
