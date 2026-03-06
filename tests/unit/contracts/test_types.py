"""Tests for core domain types."""

from __future__ import annotations

import dataclasses
from uuid import UUID, uuid4

from lintel.contracts.types import (
    ActorType,
    AgentRole,
    CorrelationId,
    EventId,
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
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            ref.workspace_id = "W2"  # type: ignore[misc]

    def test_equality(self) -> None:
        ref1 = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        ref2 = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        ref3 = ThreadRef(workspace_id="W2", channel_id="C1", thread_ts="1.0")
        assert ref1 == ref2
        assert ref1 != ref3

    def test_hashable(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        assert hash(ref) == hash(ThreadRef("W1", "C1", "1.0"))
        assert {ref} == {ThreadRef("W1", "C1", "1.0")}

    def test_stream_id_with_special_chars(self) -> None:
        ref = ThreadRef(workspace_id="T01", channel_id="C02ABC", thread_ts="1709.123456")
        assert ref.stream_id == "thread:T01:C02ABC:1709.123456"


class TestEnums:
    def test_actor_type_values(self) -> None:
        assert ActorType.HUMAN == "human"
        assert ActorType.AGENT == "agent"
        assert ActorType.SYSTEM == "system"
        assert len(ActorType) == 3

    def test_agent_role_values(self) -> None:
        expected = {"planner", "coder", "reviewer", "pm", "designer", "summarizer"}
        assert {r.value for r in AgentRole} == expected
        assert len(AgentRole) == 6

    def test_workflow_phase_values(self) -> None:
        assert WorkflowPhase.INGESTING == "ingesting"
        assert WorkflowPhase.CLOSED == "closed"
        assert len(WorkflowPhase) == 8

    def test_workflow_phase_ordering(self) -> None:
        phases = list(WorkflowPhase)
        assert phases[0] == WorkflowPhase.INGESTING
        assert phases[-1] == WorkflowPhase.CLOSED

    def test_sandbox_status_values(self) -> None:
        expected = {
            "pending",
            "creating",
            "running",
            "collecting",
            "completed",
            "failed",
            "destroyed",
        }
        assert {s.value for s in SandboxStatus} == expected
        assert len(SandboxStatus) == 7

    def test_skill_execution_mode_values(self) -> None:
        assert SkillExecutionMode.INLINE == "inline"
        assert SkillExecutionMode.ASYNC_JOB == "async_job"
        assert SkillExecutionMode.SANDBOX == "sandbox"
        assert len(SkillExecutionMode) == 3

    def test_enums_are_str_enums(self) -> None:
        assert isinstance(ActorType.HUMAN, str)
        assert isinstance(AgentRole.CODER, str)
        assert isinstance(WorkflowPhase.PLANNING, str)
        assert isinstance(SandboxStatus.RUNNING, str)
        assert isinstance(SkillExecutionMode.INLINE, str)


class TestModelPolicy:
    def test_frozen(self) -> None:
        policy = ModelPolicy(provider="anthropic", model_name="claude-3")
        with __import__("pytest").raises(dataclasses.FrozenInstanceError):
            policy.provider = "openai"  # type: ignore[misc]

    def test_defaults(self) -> None:
        policy = ModelPolicy(provider="anthropic", model_name="claude-3")
        assert policy.max_tokens == 4096
        assert policy.temperature == 0.0

    def test_custom_values(self) -> None:
        policy = ModelPolicy(
            provider="openai",
            model_name="gpt-4",
            max_tokens=8192,
            temperature=0.7,
        )
        assert policy.provider == "openai"
        assert policy.model_name == "gpt-4"
        assert policy.max_tokens == 8192
        assert policy.temperature == 0.7

    def test_equality(self) -> None:
        p1 = ModelPolicy(provider="a", model_name="b")
        p2 = ModelPolicy(provider="a", model_name="b")
        p3 = ModelPolicy(provider="a", model_name="c")
        assert p1 == p2
        assert p1 != p3


class TestNewTypes:
    def test_correlation_id_wraps_uuid(self) -> None:
        raw = uuid4()
        cid = CorrelationId(raw)
        assert cid == raw
        assert isinstance(cid, UUID)

    def test_event_id_wraps_uuid(self) -> None:
        raw = uuid4()
        eid = EventId(raw)
        assert eid == raw
        assert isinstance(eid, UUID)

    def test_newtypes_are_distinct_conceptually(self) -> None:
        raw = uuid4()
        cid = CorrelationId(raw)
        eid = EventId(raw)
        # NewType is erased at runtime, so they are equal
        # but the type checker treats them as distinct
        assert cid == eid
