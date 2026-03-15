"""In-memory store for triggers."""

from __future__ import annotations

from lintel.domain.types import Trigger


class InMemoryTriggerStore:
    """Simple in-memory store for triggers."""

    def __init__(self) -> None:
        self._triggers: dict[str, Trigger] = {}

    async def add(self, trigger: Trigger) -> None:
        self._triggers[trigger.trigger_id] = trigger

    async def get(self, trigger_id: str) -> Trigger | None:
        return self._triggers.get(trigger_id)

    async def list_all(
        self,
        project_id: str | None = None,
    ) -> list[Trigger]:
        items = list(self._triggers.values())
        if project_id is not None:
            items = [t for t in items if t.project_id == project_id]
        return items

    async def update(self, trigger: Trigger) -> None:
        if trigger.trigger_id not in self._triggers:
            msg = f"Trigger {trigger.trigger_id} not found"
            raise KeyError(msg)
        self._triggers[trigger.trigger_id] = trigger

    async def remove(self, trigger_id: str) -> None:
        if trigger_id not in self._triggers:
            msg = f"Trigger {trigger_id} not found"
            raise KeyError(msg)
        del self._triggers[trigger_id]
