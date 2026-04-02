"""Composable agent skill domain types (REQ-F033)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class SkillCategory(StrEnum):
    """Category of composable agent skill."""

    CODE_GENERATION = "code_generation"
    CODE_REVIEW = "code_review"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEPLOYMENT = "deployment"
    SECURITY = "security"
    COMMUNICATION = "communication"
    ANALYSIS = "analysis"
    CUSTOM = "custom"


@dataclass(frozen=True)
class AgentSkill:
    """A composable skill that can be attached to agent definitions."""

    skill_id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM
    version: str = "1.0.0"
    parameters_schema: dict[str, Any] = field(default_factory=dict)
    required_tools: tuple[str, ...] = ()
    active: bool = True
    project_id: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class AgentSkillBinding:
    """Binding of a skill to an agent definition with instance-specific config."""

    binding_id: str = field(default_factory=lambda: str(uuid4()))
    agent_definition_id: str = ""
    skill_id: str = ""
    configuration: dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
