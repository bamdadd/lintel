"""Agent and skill protocol definitions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lintel.agents.types import SkillDescriptor, SkillResult


class Skill(Protocol):
    """A single executable skill."""

    @property
    def descriptor(self) -> SkillDescriptor: ...

    async def execute(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult: ...


class SkillRegistry(Protocol):
    """Dynamic skill registration and discovery."""

    async def register(
        self,
        skill_id: str,
        version: str,
        name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        execution_mode: str,
    ) -> None: ...

    async def invoke(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]: ...

    async def list_skills(self) -> list[dict[str, Any]]: ...
