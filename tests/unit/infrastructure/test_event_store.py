"""Unit tests for event store serialization and row conversion."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import uuid4

from lintel.contracts.events import EventEnvelope, ThreadMessageReceived
from lintel.contracts.types import ActorType
from lintel.infrastructure.event_store.postgres import _row_to_event


class FakeRecord(dict[str, object]):
    """Mimics asyncpg.Record for unit tests."""


class TestRowToEvent:
    def test_converts_basic_row(self) -> None:
        event_id = uuid4()
        corr_id = uuid4()
        now = datetime.now(UTC)
        row = FakeRecord(
            event_id=event_id,
            event_type="ThreadMessageReceived",
            schema_version=1,
            occurred_at=now,
            actor_type="human",
            actor_id="U123",
            thread_ref=None,
            correlation_id=corr_id,
            causation_id=None,
            payload=json.dumps({"sanitized_text": "hello"}),
            idempotency_key=None,
        )
        evt = _row_to_event(row)
        assert isinstance(evt, ThreadMessageReceived)
        assert evt.event_id == event_id
        assert evt.actor_type == ActorType.HUMAN
        assert evt.payload == {"sanitized_text": "hello"}

    def test_converts_with_thread_ref(self) -> None:
        row = FakeRecord(
            event_id=uuid4(),
            event_type="ThreadMessageReceived",
            schema_version=1,
            occurred_at=datetime.now(UTC),
            actor_type="system",
            actor_id="sys",
            thread_ref=json.dumps(
                {
                    "workspace_id": "W1",
                    "channel_id": "C1",
                    "thread_ts": "1.0",
                }
            ),
            correlation_id=uuid4(),
            causation_id=None,
            payload="{}",
            idempotency_key=None,
        )
        evt = _row_to_event(row)
        assert evt.thread_ref is not None
        assert evt.thread_ref.workspace_id == "W1"

    def test_converts_dict_payload(self) -> None:
        row = FakeRecord(
            event_id=uuid4(),
            event_type="EventEnvelope",
            schema_version=1,
            occurred_at=datetime.now(UTC),
            actor_type="system",
            actor_id="sys",
            thread_ref=None,
            correlation_id=uuid4(),
            causation_id=None,
            payload={"key": "value"},
            idempotency_key=None,
        )
        evt = _row_to_event(row)
        assert isinstance(evt, EventEnvelope)
        assert evt.payload == {"key": "value"}

    def test_unknown_event_type_returns_envelope(self) -> None:
        row = FakeRecord(
            event_id=uuid4(),
            event_type="UnknownFutureEvent",
            schema_version=1,
            occurred_at=datetime.now(UTC),
            actor_type="system",
            actor_id="sys",
            thread_ref=None,
            correlation_id=uuid4(),
            causation_id=None,
            payload="{}",
            idempotency_key=None,
        )
        evt = _row_to_event(row)
        assert type(evt) is EventEnvelope
        assert evt.event_type == "UnknownFutureEvent"

    def test_preserves_causation_id(self) -> None:
        cause_id = uuid4()
        row = FakeRecord(
            event_id=uuid4(),
            event_type="ThreadMessageReceived",
            schema_version=1,
            occurred_at=datetime.now(UTC),
            actor_type="human",
            actor_id="U1",
            thread_ref=None,
            correlation_id=uuid4(),
            causation_id=cause_id,
            payload="{}",
            idempotency_key=None,
        )
        evt = _row_to_event(row)
        assert evt.causation_id == cause_id

    def test_preserves_idempotency_key(self) -> None:
        row = FakeRecord(
            event_id=uuid4(),
            event_type="ThreadMessageReceived",
            schema_version=1,
            occurred_at=datetime.now(UTC),
            actor_type="system",
            actor_id="sys",
            thread_ref=None,
            correlation_id=uuid4(),
            causation_id=None,
            payload="{}",
            idempotency_key="msg-abc-123",
        )
        evt = _row_to_event(row)
        assert evt.idempotency_key == "msg-abc-123"

    def test_preserves_schema_version(self) -> None:
        row = FakeRecord(
            event_id=uuid4(),
            event_type="ThreadMessageReceived",
            schema_version=2,
            occurred_at=datetime.now(UTC),
            actor_type="system",
            actor_id="sys",
            thread_ref=None,
            correlation_id=uuid4(),
            causation_id=None,
            payload="{}",
            idempotency_key=None,
        )
        evt = _row_to_event(row)
        assert evt.schema_version == 2

    def test_dict_thread_ref(self) -> None:
        row = FakeRecord(
            event_id=uuid4(),
            event_type="ThreadMessageReceived",
            schema_version=1,
            occurred_at=datetime.now(UTC),
            actor_type="human",
            actor_id="U1",
            thread_ref={
                "workspace_id": "W2",
                "channel_id": "C2",
                "thread_ts": "2.0",
            },
            correlation_id=uuid4(),
            causation_id=None,
            payload="{}",
            idempotency_key=None,
        )
        evt = _row_to_event(row)
        assert evt.thread_ref is not None
        assert evt.thread_ref.channel_id == "C2"
