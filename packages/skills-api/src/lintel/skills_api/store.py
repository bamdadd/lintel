"""In-memory skill store."""

from __future__ import annotations

from typing import Any

from lintel.agents.types import (
    SkillDescriptor,
    SkillExecutionMode,
    SkillResult,
)


class InMemorySkillStore:
    """Minimal in-memory store satisfying the SkillRegistry protocol shape."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDescriptor] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    async def register(
        self,
        skill_id: str,
        version: str,
        name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        execution_mode: str,
        description: str = "",
        allowed_agent_roles: tuple[str, ...] | list[str] = (),
    ) -> SkillDescriptor:
        descriptor = SkillDescriptor(
            name=name,
            version=version,
            description=description,
            input_schema=input_schema,
            output_schema=output_schema,
            execution_mode=SkillExecutionMode(execution_mode),
            allowed_agent_roles=frozenset(allowed_agent_roles),
        )
        self._skills[skill_id] = descriptor
        return descriptor

    async def invoke(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        if skill_id not in self._skills:
            msg = f"Skill {skill_id} not found"
            raise KeyError(msg)
        # Stub: real implementation would dispatch to the skill runtime.
        return SkillResult(success=True, output={"echo": input_data})

    async def delete(self, skill_id: str) -> None:
        if skill_id not in self._skills:
            msg = f"Skill {skill_id} not found"
            raise KeyError(msg)
        del self._skills[skill_id]
        self._metadata.pop(skill_id, None)

    async def list_skills(self) -> dict[str, SkillDescriptor]:
        return dict(self._skills)
