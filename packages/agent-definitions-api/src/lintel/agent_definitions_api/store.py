"""In-memory store for agent definitions."""

from __future__ import annotations

from typing import Any

from lintel.persistence.data_models import AgentDefinitionData


class AgentDefinitionStore:
    """In-memory store for user-defined agent definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, Any]] = {}

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._definitions.values())

    async def get(self, agent_id: str) -> dict[str, Any] | None:
        return self._definitions.get(agent_id)

    async def create(self, definition: dict[str, Any]) -> dict[str, Any]:
        validated = AgentDefinitionData.model_validate(definition)
        agent_id = validated.agent_id
        if agent_id in self._definitions:
            msg = f"Agent definition '{agent_id}' already exists"
            raise ValueError(msg)
        data = validated.model_dump()
        self._definitions[agent_id] = data
        return data

    async def update(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        if agent_id not in self._definitions:
            raise KeyError(agent_id)
        self._definitions[agent_id].update(updates)
        return self._definitions[agent_id]

    async def delete(self, agent_id: str) -> None:
        if agent_id not in self._definitions:
            raise KeyError(agent_id)
        del self._definitions[agent_id]
