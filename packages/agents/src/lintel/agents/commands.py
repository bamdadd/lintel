"""Agent command schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from lintel.agents.types import AgentRole
    from lintel.contracts.types import ThreadRef


@dataclass(frozen=True)
class ScheduleAgentStep:
    thread_ref: ThreadRef
    agent_role: AgentRole
    step_name: str
    context: dict[str, object] = field(default_factory=dict)
    correlation_id: UUID = field(default_factory=uuid4)


@dataclass(frozen=True)
class ScheduleSandboxJob:
    thread_ref: ThreadRef
    agent_role: AgentRole
    repo_url: str
    base_sha: str
    commands: list[str] = field(default_factory=list)
    correlation_id: UUID = field(default_factory=uuid4)
