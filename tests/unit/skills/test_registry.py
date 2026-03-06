"""Tests for the skill registry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from lintel.contracts.types import SkillDescriptor, SkillResult
from lintel.domain.skills.registry import InMemorySkillRegistry


@dataclass
class FakeSkill:
    """Test skill implementation."""

    _descriptor: SkillDescriptor

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    async def execute(
        self,
        inputs: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        return SkillResult(success=True, output={"echo": inputs})


def _make_skill(
    name: str = "test_skill",
    version: str = "1.0.0",
    roles: frozenset[str] = frozenset({"coder"}),
) -> FakeSkill:
    return FakeSkill(
        _descriptor=SkillDescriptor(
            name=name,
            version=version,
            description="A test skill",
            allowed_agent_roles=roles,
        ),
    )


class TestInMemorySkillRegistry:
    async def test_register_and_get(self) -> None:
        registry = InMemorySkillRegistry()
        skill = _make_skill()
        await registry.register(skill)
        result = await registry.get("test_skill")
        assert result is skill

    async def test_get_nonexistent_raises(self) -> None:
        registry = InMemorySkillRegistry()
        with pytest.raises(KeyError, match="Skill not found"):
            await registry.get("nonexistent")

    async def test_get_specific_version(self) -> None:
        registry = InMemorySkillRegistry()
        v1 = _make_skill(version="1.0.0")
        v2 = _make_skill(version="2.0.0")
        await registry.register(v1)
        await registry.register(v2)
        result = await registry.get("test_skill", "1.0.0")
        assert result is v1

    async def test_get_latest_version(self) -> None:
        registry = InMemorySkillRegistry()
        v1 = _make_skill(version="1.0.0")
        v2 = _make_skill(version="2.0.0")
        await registry.register(v1)
        await registry.register(v2)
        result = await registry.get("test_skill")
        assert result is v2

    async def test_deregister(self) -> None:
        registry = InMemorySkillRegistry()
        skill = _make_skill()
        await registry.register(skill)
        await registry.deregister("test_skill", "1.0.0")
        with pytest.raises(KeyError):
            await registry.get("test_skill")

    async def test_list_skills(self) -> None:
        registry = InMemorySkillRegistry()
        await registry.register(_make_skill(name="a"))
        await registry.register(_make_skill(name="b"))
        skills = await registry.list_skills()
        assert len(skills) == 2
        names = {s.name for s in skills}
        assert names == {"a", "b"}

    async def test_list_for_agent_filters_by_role(self) -> None:
        registry = InMemorySkillRegistry()
        await registry.register(_make_skill(name="coder_skill", roles=frozenset({"coder"})))
        await registry.register(
            _make_skill(name="reviewer_skill", roles=frozenset({"reviewer"})),
        )
        coder_skills = await registry.list_for_agent("coder")
        assert len(coder_skills) == 1
        assert coder_skills[0].name == "coder_skill"
