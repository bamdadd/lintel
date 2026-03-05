"""Tests for core domain types."""

from __future__ import annotations

import dataclasses

from lintel.contracts.types import (
    ActorType,
    AgentRole,
    ModelPolicy,
    SandboxStatus,
    SkillExecutionMode,
    ThreadRef,
    WorkflowPhase,
)


class TestThreadRef:
    def test_stream_id_format(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
        assert ref.stream_id == "thread:W1:C1:123.456"

    def test_str_returns_stream_id(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
        assert str(ref) == ref.stream_id

    def test_frozen(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="123.456")
        assert dataclasses.is_dataclass(ref)
        try:
            ref.workspace_id = "W2"  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except dataclasses.FrozenInstanceError:
            pass


class TestEnums:
    def test_actor_type_values(self) -> None:
        assert ActorType.HUMAN == "human"
        assert ActorType.AGENT == "agent"
        assert ActorType.SYSTEM == "system"

    def test_agent_role_values(self) -> None:
        assert len(AgentRole) == 6

    def test_workflow_phase_values(self) -> None:
        assert WorkflowPhase.INGESTING == "ingesting"
        assert WorkflowPhase.CLOSED == "closed"

    def test_sandbox_status_values(self) -> None:
        assert len(SandboxStatus) == 7

    def test_skill_execution_mode_values(self) -> None:
        assert SkillExecutionMode.INLINE == "inline"
        assert SkillExecutionMode.SANDBOX == "sandbox"


class TestModelPolicy:
    def test_frozen(self) -> None:
        policy = ModelPolicy(provider="anthropic", model_name="claude-3")
        try:
            policy.provider = "openai"  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except dataclasses.FrozenInstanceError:
            pass

    def test_defaults(self) -> None:
        policy = ModelPolicy(provider="anthropic", model_name="claude-3")
        assert policy.max_tokens == 4096
        assert policy.temperature == 0.0
