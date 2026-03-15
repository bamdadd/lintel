"""Skill protocol definitions."""

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
