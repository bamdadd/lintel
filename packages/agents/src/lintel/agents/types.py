"""Agent and skill domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AgentCategory(StrEnum):
    ENGINEERING = "engineering"
    QUALITY = "quality"
    OPERATIONS = "operations"
    LEADERSHIP = "leadership"
    COMMUNICATION = "communication"
    DESIGN = "design"


class AgentRole(StrEnum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    PM = "pm"
    DESIGNER = "designer"
    SUMMARIZER = "summarizer"
    ARCHITECT = "architect"
    QA_ENGINEER = "qa_engineer"
    DEVOPS = "devops"
    SECURITY = "security"
    RESEARCHER = "researcher"
    TECH_LEAD = "tech_lead"
    DOCUMENTATION = "documentation"
    TRIAGE = "triage"


class SkillExecutionMode(StrEnum):
    INLINE = "inline"
    ASYNC_JOB = "async_job"
    SANDBOX = "sandbox"


@dataclass(frozen=True)
class SkillDescriptor:
    """Metadata describing a registered skill."""

    name: str
    version: str
    description: str = ""
    input_schema: dict[str, object] | None = None
    output_schema: dict[str, object] | None = None
    execution_mode: SkillExecutionMode = SkillExecutionMode.INLINE
    allowed_agent_roles: frozenset[str] = frozenset()


@dataclass(frozen=True)
class SkillResult:
    """Result of a skill invocation."""

    success: bool
    output: dict[str, object] | None = None
    error: str | None = None


@dataclass(frozen=True)
class AgentSession:
    """Tracks an agent's execution within a pipeline stage."""

    session_id: str
    run_id: str
    stage_id: str
    agent_role: str
    messages: tuple[dict[str, object], ...] = ()
    tool_calls: tuple[dict[str, object], ...] = ()
    token_usage: dict[str, int] | None = None
    model_used: str = ""


class SkillCategory(StrEnum):
    CODE_GENERATION = "code_generation"
    CODE_ANALYSIS = "code_analysis"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    DEVOPS = "devops"
    SECURITY = "security"
    PROJECT_MANAGEMENT = "project_management"
    DESIGN = "design"
    COMMUNICATION = "communication"
    DATA = "data"
    CUSTOM = "custom"


@dataclass(frozen=True)
class SkillDefinition:
    """A user-editable skill definition that agents can use."""

    skill_id: str
    name: str
    version: str
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM
    system_prompt: str = ""
    user_prompt_template: str = ""
    input_schema: dict[str, object] | None = None
    output_schema: dict[str, object] | None = None
    execution_mode: SkillExecutionMode = SkillExecutionMode.INLINE
    allowed_agent_roles: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    is_builtin: bool = False
    enabled: bool = True


@dataclass(frozen=True)
class AgentDefinitionRecord:
    """A user-editable agent definition persisted to the database."""

    agent_id: str
    name: str
    role: str
    category: str = AgentCategory.ENGINEERING
    description: str = ""
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0
    allowed_skill_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    is_builtin: bool = False
    enabled: bool = True
