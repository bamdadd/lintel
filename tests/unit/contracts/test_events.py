"""Tests for event envelope and event types."""

from __future__ import annotations

import dataclasses
from uuid import UUID

from lintel.contracts.events import (
    EVENT_TYPE_MAP,
    AgentStepCompleted,
    AgentStepScheduled,
    AgentStepStarted,
    BranchCreated,
    EventEnvelope,
    HumanApprovalGranted,
    HumanApprovalRejected,
    IntentRouted,
    ModelCallCompleted,
    ModelSelected,
    PIIAnonymised,
    PIIDetected,
    PIIResidualRiskBlocked,
    PolicyDecisionRecorded,
    PRCreated,
    SandboxArtifactsCollected,
    SandboxCreated,
    SandboxDestroyed,
    SandboxJobScheduled,
    ThreadMessageReceived,
    VaultRevealGranted,
    VaultRevealRequested,
    WorkflowAdvanced,
    WorkflowStarted,
    deserialize_event,
)
from lintel.contracts.types import ActorType, ThreadRef


class TestEventEnvelope:
    def test_frozen(self) -> None:
        env = EventEnvelope()
        try:
            env.event_type = "foo"  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except dataclasses.FrozenInstanceError:
            pass

    def test_defaults(self) -> None:
        env = EventEnvelope()
        assert isinstance(env.event_id, UUID)
        assert env.event_type == ""
        assert env.schema_version == 1
        assert env.actor_type == ActorType.SYSTEM
        assert env.payload == {}

    def test_correlation_id_generated(self) -> None:
        e1 = EventEnvelope()
        e2 = EventEnvelope()
        assert e1.correlation_id != e2.correlation_id


class TestConcreteEvents:
    def test_thread_message_received_type(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        evt = ThreadMessageReceived(thread_ref=ref, actor_type=ActorType.HUMAN)
        assert evt.event_type == "ThreadMessageReceived"

    def test_all_event_types_have_correct_event_type(self) -> None:
        event_classes = [
            ThreadMessageReceived,
            PIIDetected,
            PIIAnonymised,
            PIIResidualRiskBlocked,
            IntentRouted,
            WorkflowStarted,
            WorkflowAdvanced,
            AgentStepScheduled,
            AgentStepStarted,
            AgentStepCompleted,
            ModelSelected,
            ModelCallCompleted,
            SandboxJobScheduled,
            SandboxCreated,
            SandboxArtifactsCollected,
            SandboxDestroyed,
            BranchCreated,
            PRCreated,
            HumanApprovalGranted,
            HumanApprovalRejected,
            VaultRevealRequested,
            VaultRevealGranted,
            PolicyDecisionRecorded,
        ]
        for cls in event_classes:
            evt = cls()
            assert evt.event_type == cls.__name__, f"{cls.__name__} has wrong event_type"

    def test_all_events_are_frozen(self) -> None:
        for cls in EVENT_TYPE_MAP.values():
            evt = cls()
            try:
                evt.event_type = "modified"  # type: ignore[misc]
                raise AssertionError(f"{cls.__name__} should be frozen")
            except dataclasses.FrozenInstanceError:
                pass


class TestEventTypeMap:
    def test_completeness(self) -> None:
        assert len(EVENT_TYPE_MAP) == 23

    def test_all_keys_match_class_names(self) -> None:
        for key, cls in EVENT_TYPE_MAP.items():
            assert key == cls.__name__


class TestDeserializeEvent:
    def test_round_trip(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        original = ThreadMessageReceived(
            thread_ref=ref,
            actor_type=ActorType.HUMAN,
            payload={"sanitized_text": "hello"},
        )
        data = dataclasses.asdict(original)
        restored = deserialize_event("ThreadMessageReceived", data)
        assert restored.event_type == "ThreadMessageReceived"
        assert restored.payload == {"sanitized_text": "hello"}

    def test_unknown_type_raises(self) -> None:
        try:
            deserialize_event("UnknownEvent", {})
            raise AssertionError("Should raise KeyError")
        except KeyError:
            pass
