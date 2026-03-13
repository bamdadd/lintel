"""Tests for InMemoryEventStore."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from lintel.contracts.events import EventEnvelope, ThreadMessageReceived, WorkflowStarted
from lintel.contracts.types import ThreadRef
from lintel.infrastructure.event_store.in_memory import InMemoryEventStore

THREAD = ThreadRef("ws1", "ch1", "ts1")


class TestInMemoryEventStore:
    def setup_method(self) -> None:
        self.store = InMemoryEventStore()

    async def test_append_and_read(self) -> None:
        event = ThreadMessageReceived(thread_ref=THREAD, payload={"text": "hello"})
        await self.store.append("stream-1", [event])
        events = await self.store.read_stream("stream-1")
        assert len(events) == 1
        assert events[0].event_type == "ThreadMessageReceived"

    async def test_read_empty_stream(self) -> None:
        events = await self.store.read_stream("nonexistent")
        assert events == []

    async def test_append_multiple_events(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        e2 = WorkflowStarted(thread_ref=THREAD, payload={})
        await self.store.append("stream-1", [e1, e2])
        events = await self.store.read_stream("stream-1")
        assert len(events) == 2

    async def test_read_from_version(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        e2 = WorkflowStarted(thread_ref=THREAD, payload={})
        await self.store.append("stream-1", [e1, e2])
        events = await self.store.read_stream("stream-1", from_version=1)
        assert len(events) == 1
        assert events[0].event_type == "WorkflowStarted"

    async def test_expected_version_success(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        await self.store.append("stream-1", [e1])
        e2 = WorkflowStarted(thread_ref=THREAD, payload={})
        await self.store.append("stream-1", [e2], expected_version=0)
        events = await self.store.read_stream("stream-1")
        assert len(events) == 2

    async def test_expected_version_conflict(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        await self.store.append("stream-1", [e1])
        e2 = WorkflowStarted(thread_ref=THREAD, payload={})
        with pytest.raises(ValueError, match="Expected version"):
            await self.store.append("stream-1", [e2], expected_version=5)

    async def test_read_all_across_streams(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        e2 = WorkflowStarted(thread_ref=ThreadRef("ws2", "ch2", "ts2"), payload={})
        await self.store.append("stream-1", [e1])
        await self.store.append("stream-2", [e2])
        all_events = await self.store.read_all()
        assert len(all_events) == 2

    async def test_read_all_with_limit(self) -> None:
        for i in range(5):
            await self.store.append(f"s-{i}", [EventEnvelope(payload={"i": i})])
        events = await self.store.read_all(limit=3)
        assert len(events) == 3

    async def test_read_by_correlation(self) -> None:
        cid = uuid4()
        e1 = ThreadMessageReceived(correlation_id=cid, thread_ref=THREAD, payload={})
        e2 = WorkflowStarted(correlation_id=cid, thread_ref=THREAD, payload={})
        e3 = ThreadMessageReceived(thread_ref=THREAD, payload={})  # different cid
        await self.store.append("stream-1", [e1, e2, e3])
        events = await self.store.read_by_correlation(cid)
        assert len(events) == 2
        assert all(e.correlation_id == cid for e in events)

    async def test_multiple_streams_isolated(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        e2 = WorkflowStarted(thread_ref=THREAD, payload={})
        await self.store.append("stream-a", [e1])
        await self.store.append("stream-b", [e2])
        assert len(await self.store.read_stream("stream-a")) == 1
        assert len(await self.store.read_stream("stream-b")) == 1

    # --- EVT-3.1: read_by_event_type ---

    async def test_read_by_event_type(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        e2 = WorkflowStarted(thread_ref=THREAD, payload={})
        e3 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        await self.store.append("stream-1", [e1, e2, e3])
        results = await self.store.read_by_event_type("ThreadMessageReceived")
        assert len(results) == 2
        assert all(e.event_type == "ThreadMessageReceived" for e in results)

    async def test_read_by_event_type_with_limit(self) -> None:
        for i in range(5):
            await self.store.append(
                f"s-{i}", [ThreadMessageReceived(thread_ref=THREAD, payload={"i": i})]
            )
        results = await self.store.read_by_event_type("ThreadMessageReceived", limit=3)
        assert len(results) == 3

    async def test_read_by_event_type_from_position(self) -> None:
        events = [ThreadMessageReceived(thread_ref=THREAD, payload={"i": i}) for i in range(5)]
        await self.store.append("stream-1", events)
        all_typed = await self.store.read_by_event_type("ThreadMessageReceived")
        assert len(all_typed) == 5
        mid_pos = all_typed[2].global_position
        assert mid_pos is not None
        from_mid = await self.store.read_by_event_type(
            "ThreadMessageReceived", from_position=mid_pos
        )
        assert len(from_mid) == 3
        assert all(
            e.global_position is not None and e.global_position >= mid_pos for e in from_mid
        )

    async def test_read_by_event_type_empty(self) -> None:
        results = await self.store.read_by_event_type("NonExistent")
        assert results == []

    # --- EVT-3.2: read_by_time_range ---

    async def test_read_by_time_range(self) -> None:
        now = datetime.now(UTC)
        e1 = ThreadMessageReceived(
            thread_ref=THREAD, occurred_at=now - timedelta(hours=2), payload={}
        )
        e2 = ThreadMessageReceived(
            thread_ref=THREAD, occurred_at=now - timedelta(hours=1), payload={}
        )
        e3 = ThreadMessageReceived(
            thread_ref=THREAD, occurred_at=now + timedelta(hours=1), payload={}
        )
        await self.store.append("stream-1", [e1, e2, e3])

        results = await self.store.read_by_time_range(
            from_time=now - timedelta(hours=3),
            to_time=now,
        )
        assert len(results) == 2

    async def test_read_by_time_range_with_event_types(self) -> None:
        now = datetime.now(UTC)
        e1 = ThreadMessageReceived(thread_ref=THREAD, occurred_at=now, payload={})
        e2 = WorkflowStarted(thread_ref=THREAD, occurred_at=now, payload={})
        await self.store.append("stream-1", [e1, e2])

        results = await self.store.read_by_time_range(
            from_time=now - timedelta(seconds=1),
            to_time=now + timedelta(seconds=1),
            event_types=frozenset({"ThreadMessageReceived"}),
        )
        assert len(results) == 1
        assert results[0].event_type == "ThreadMessageReceived"

    async def test_read_by_time_range_empty(self) -> None:
        far_past = datetime(2020, 1, 1, tzinfo=UTC)
        results = await self.store.read_by_time_range(
            from_time=far_past,
            to_time=far_past + timedelta(seconds=1),
        )
        assert results == []

    # --- EVT-3.3: global_position ---

    async def test_global_position_assigned(self) -> None:
        e1 = ThreadMessageReceived(thread_ref=THREAD, payload={})
        e2 = WorkflowStarted(thread_ref=THREAD, payload={})
        await self.store.append("stream-a", [e1])
        await self.store.append("stream-b", [e2])
        all_events = await self.store.read_all()
        assert len(all_events) == 2
        assert all_events[0].global_position == 1
        assert all_events[1].global_position == 2

    async def test_global_position_monotonically_increasing(self) -> None:
        for i in range(5):
            await self.store.append(
                f"s-{i}", [EventEnvelope(payload={"i": i})]
            )
        all_events = await self.store.read_all()
        positions = [e.global_position for e in all_events]
        assert positions == [1, 2, 3, 4, 5]

    async def test_read_all_from_position_uses_global_position(self) -> None:
        for i in range(5):
            await self.store.append(
                f"s-{i}", [EventEnvelope(payload={"i": i})]
            )
        # global_positions will be 1..5
        from_3 = await self.store.read_all(from_position=3)
        assert len(from_3) == 3
        assert [e.global_position for e in from_3] == [3, 4, 5]
