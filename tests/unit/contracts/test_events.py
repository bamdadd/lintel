"""Tests for event envelope and event types."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

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
        with pytest.raises(dataclasses.FrozenInstanceError):
            env.event_type = "foo"  # type: ignore[misc]

    def test_defaults(self) -> None:
        env = EventEnvelope()
        assert isinstance(env.event_id, UUID)
        assert env.event_type == ""
        assert env.schema_version == 1
        assert env.actor_type == ActorType.SYSTEM
        assert env.actor_id == ""
        assert env.thread_ref is None
        assert env.causation_id is None
        assert env.payload == {}
        assert env.idempotency_key is None

    def test_correlation_id_generated(self) -> None:
        e1 = EventEnvelope()
        e2 = EventEnvelope()
        assert e1.correlation_id != e2.correlation_id

    def test_event_id_unique_per_instance(self) -> None:
        e1 = EventEnvelope()
        e2 = EventEnvelope()
        assert e1.event_id != e2.event_id

    def test_occurred_at_is_utc(self) -> None:
        env = EventEnvelope()
        assert env.occurred_at.tzinfo is not None
        now = datetime.now(UTC)
        assert abs(env.occurred_at - now) < timedelta(seconds=2)

    def test_causation_id_chaining(self) -> None:
        parent = EventEnvelope()
        child = EventEnvelope(
            causation_id=parent.event_id,
            correlation_id=parent.correlation_id,
        )
        assert child.causation_id == parent.event_id
        assert child.correlation_id == parent.correlation_id

    def test_idempotency_key(self) -> None:
        key = "msg-abc-123"
        env = EventEnvelope(idempotency_key=key)
        assert env.idempotency_key == key

    def test_custom_payload(self) -> None:
        env = EventEnvelope(payload={"foo": "bar", "count": 42})
        assert env.payload["foo"] == "bar"
        assert env.payload["count"] == 42

    def test_with_thread_ref(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        env = EventEnvelope(thread_ref=ref)
        assert env.thread_ref is not None
        assert env.thread_ref.stream_id == "thread:W1:C1:1.0"


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
            with pytest.raises(dataclasses.FrozenInstanceError):
                evt.event_type = "modified"  # type: ignore[misc]

    def test_all_events_inherit_envelope(self) -> None:
        for cls in EVENT_TYPE_MAP.values():
            assert issubclass(cls, EventEnvelope)

    def test_concrete_event_preserves_envelope_fields(self) -> None:
        ref = ThreadRef(workspace_id="W1", channel_id="C1", thread_ts="1.0")
        corr_id = uuid4()
        cause_id = uuid4()
        evt = ThreadMessageReceived(
            actor_type=ActorType.HUMAN,
            actor_id="U123",
            thread_ref=ref,
            correlation_id=corr_id,
            causation_id=cause_id,
            payload={"text": "hello"},
            idempotency_key="key-1",
        )
        assert evt.actor_type == ActorType.HUMAN
        assert evt.actor_id == "U123"
        assert evt.thread_ref == ref
        assert evt.correlation_id == corr_id
        assert evt.causation_id == cause_id
        assert evt.payload == {"text": "hello"}
        assert evt.idempotency_key == "key-1"


class TestEventTypeMap:
    def test_completeness(self) -> None:
        assert len(EVENT_TYPE_MAP) == 26

    def test_all_keys_match_class_names(self) -> None:
        for key, cls in EVENT_TYPE_MAP.items():
            assert key == cls.__name__

    def test_no_base_envelope_in_map(self) -> None:
        assert "" not in EVENT_TYPE_MAP
        assert "EventEnvelope" not in EVENT_TYPE_MAP


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
        with pytest.raises(KeyError):
            deserialize_event("UnknownEvent", {})

    def test_round_trip_preserves_ids(self) -> None:
        original = ThreadMessageReceived(
            actor_type=ActorType.SYSTEM,
            actor_id="sys",
            payload={"text": "test"},
        )
        data = dataclasses.asdict(original)
        restored = deserialize_event("ThreadMessageReceived", data)
        assert restored.event_id == original.event_id
        assert restored.correlation_id == original.correlation_id

    def test_round_trip_preserves_causation(self) -> None:
        cause = uuid4()
        original = WorkflowStarted(
            causation_id=cause,
            payload={"workflow_type": "feature"},
        )
        data = dataclasses.asdict(original)
        restored = deserialize_event("WorkflowStarted", data)
        assert restored.causation_id == cause
