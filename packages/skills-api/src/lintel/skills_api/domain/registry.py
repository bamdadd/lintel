"""In-memory skill registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.agents.protocols import Skill
    from lintel.agents.types import SkillDescriptor


class InMemorySkillRegistry:
    """Implements SkillRegistry protocol with in-memory storage."""

    def __init__(self) -> None:
        self._skills: dict[str, dict[str, Skill]] = {}

    async def register(self, skill: Skill) -> None:
        desc = skill.descriptor
        self._skills.setdefault(desc.name, {})[desc.version] = skill

    async def deregister(self, skill_name: str, version: str) -> None:
        if skill_name in self._skills:
            self._skills[skill_name].pop(version, None)

    async def get(self, skill_name: str, version: str | None = None) -> Skill:
        versions = self._skills.get(skill_name)
        if not versions:
            msg = f"Skill not found: {skill_name}"
            raise KeyError(msg)
        if version:
            return versions[version]
        latest = sorted(versions.keys())[-1]
        return versions[latest]

    async def list_skills(self) -> list[SkillDescriptor]:
        return [
            skill.descriptor for versions in self._skills.values() for skill in versions.values()
        ]

    async def list_for_agent(self, agent_role: str) -> list[SkillDescriptor]:
        return [d for d in await self.list_skills() if agent_role in d.allowed_agent_roles]
