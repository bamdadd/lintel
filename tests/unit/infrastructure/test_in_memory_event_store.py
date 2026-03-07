"""Tests for InMemoryEventStore."""

from __future__ import annotations

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
