"""In-memory stores for agent skills and bindings."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from lintel.agent_skills_api.types import AgentSkill, AgentSkillBinding


def _skill_to_dict(s: AgentSkill) -> dict[str, Any]:
    """Convert an AgentSkill dataclass to a JSON-friendly dict."""
    d = asdict(s)
    d["created_at"] = s.created_at.isoformat()
    d["updated_at"] = s.updated_at.isoformat()
    d["required_tools"] = list(s.required_tools)
    return d


def _binding_to_dict(b: AgentSkillBinding) -> dict[str, Any]:
    """Convert an AgentSkillBinding dataclass to a JSON-friendly dict."""
    d = asdict(b)
    d["created_at"] = b.created_at.isoformat()
    return d


class InMemoryAgentSkillStore:
    """Simple in-memory store for agent skills."""

    def __init__(self) -> None:
        self._skills: dict[str, AgentSkill] = {}

    async def get(self, skill_id: str) -> dict[str, Any] | None:
        s = self._skills.get(skill_id)
        if s is None:
            return None
        return _skill_to_dict(s)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_skill_to_dict(s) for s in self._skills.values()]

    async def add(self, skill: AgentSkill) -> dict[str, Any]:
        self._skills[skill.skill_id] = skill
        return _skill_to_dict(skill)

    async def update(self, skill_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        s = self._skills.get(skill_id)
        if s is None:
            return None
        data = asdict(s)
        data.update(updates)
        if "required_tools" in updates:
            data["required_tools"] = tuple(data["required_tools"])
        updated = AgentSkill(**data)
        self._skills[skill_id] = updated
        return _skill_to_dict(updated)

    async def remove(self, skill_id: str) -> bool:
        if skill_id not in self._skills:
            return False
        del self._skills[skill_id]
        return True


class InMemoryAgentSkillBindingStore:
    """Simple in-memory store for agent skill bindings."""

    def __init__(self) -> None:
        self._bindings: dict[str, AgentSkillBinding] = {}

    async def get(self, binding_id: str) -> dict[str, Any] | None:
        b = self._bindings.get(binding_id)
        if b is None:
            return None
        return _binding_to_dict(b)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_binding_to_dict(b) for b in self._bindings.values()]

    async def list_by_agent(self, agent_definition_id: str) -> list[dict[str, Any]]:
        return [
            _binding_to_dict(b)
            for b in self._bindings.values()
            if b.agent_definition_id == agent_definition_id
        ]

    async def add(self, binding: AgentSkillBinding) -> dict[str, Any]:
        self._bindings[binding.binding_id] = binding
        return _binding_to_dict(binding)

    async def remove(self, binding_id: str) -> bool:
        if binding_id not in self._bindings:
            return False
        del self._bindings[binding_id]
        return True
