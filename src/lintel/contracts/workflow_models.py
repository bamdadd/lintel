"""Pydantic models for workflow node data structures.

These replace raw dict[str, Any] usage throughout workflow nodes,
agent runtime, and helper functions. All models use frozen=True
for immutability, matching the project's dataclass conventions.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Token usage tracking
# ---------------------------------------------------------------------------


class TokenUsage(BaseModel):
    """Token usage from a single LLM call or aggregated across a node."""

    model_config = ConfigDict(frozen=True)

    node: str = ""
    step: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


# ---------------------------------------------------------------------------
# Agent runtime results
# ---------------------------------------------------------------------------


class AgentStepResult(BaseModel):
    """Result from AgentRuntime.execute_step() or execute_step_stream()."""

    model_config = ConfigDict(frozen=True)

    content: str = ""
    model: str = ""
    usage: TokenUsage = Field(default_factory=TokenUsage)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_iterations: int = 0


# ---------------------------------------------------------------------------
# Plan structures
# ---------------------------------------------------------------------------


class PlanTask(BaseModel):
    """A single task within an implementation plan."""

    model_config = ConfigDict(frozen=True, extra="allow")

    title: str = ""
    description: str = ""
    file_paths: list[str] = Field(default_factory=list)
    complexity: str = ""


class Plan(BaseModel):
    """Implementation plan produced by the plan node."""

    model_config = ConfigDict(frozen=True)

    tasks: list[PlanTask] = Field(default_factory=list)
    summary: str = ""
    intent: str = ""


# ---------------------------------------------------------------------------
# Triage structures
# ---------------------------------------------------------------------------


class TriageResult(BaseModel):
    """Classification result from the triage node."""

    model_config = ConfigDict(frozen=True)

    type: str = "feature"
    priority: str = "P2"
    severity: str = "medium"
    summary: str = ""
    suggested_agents: list[str] = Field(default_factory=lambda: ["planner", "coder"])


# ---------------------------------------------------------------------------
# Agent output (stored in state.agent_outputs)
# ---------------------------------------------------------------------------


class AgentOutput(BaseModel):
    """Output from a workflow node, stored in state.agent_outputs."""

    model_config = ConfigDict(frozen=True, extra="allow")

    node: str
    agent: str = ""
    content: str = ""
    summary: str = ""
    output: str = ""
    error: str = ""
    verdict: str = ""
    exit_code: int | None = None
    classification: str = ""
    priority: str = ""


# ---------------------------------------------------------------------------
# Rebase result
# ---------------------------------------------------------------------------


class RebaseResult(BaseModel):
    """Result from a git rebase operation."""

    model_config = ConfigDict(frozen=True)

    success: bool
    message: str = ""


# ---------------------------------------------------------------------------
# Test discovery
# ---------------------------------------------------------------------------


class TestDiscoveryResult(BaseModel):
    """Result from the test command discovery skill."""

    model_config = ConfigDict(frozen=True)

    test_command: str
    setup_commands: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Sandbox capabilities
# ---------------------------------------------------------------------------


class SandboxCapabilities(BaseModel):
    """Available services/tools detected in a sandbox."""

    model_config = ConfigDict(frozen=True)

    postgres: bool = False
    redis: bool = False
    docker: bool = False
    uv: bool = False
    node: bool = False


# ---------------------------------------------------------------------------
# Dev commands (discovered for TDD mode)
# ---------------------------------------------------------------------------


class DevCommands(BaseModel):
    """Development commands discovered for a project."""

    model_config = ConfigDict(frozen=True)

    test_command: str = "echo 'no test command'"
    lint_command: str = "echo 'no lint configured'"
    typecheck_command: str = "echo 'no typecheck'"
    test_single_command: str = ""
