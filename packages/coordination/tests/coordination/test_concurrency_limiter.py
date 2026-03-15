"""Unit tests for ConcurrencyLimiter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from lintel.contracts.concurrency import ConcurrencyState, SlotAcquiredEvent, SlotReleasedEvent


class TestConcurrencyLimiterAcquireRelease:
    async def test_acquire_publishes_slot_acquired_event(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=2, event_bus=bus)
        agent_id = "agent-1"
        run_id = uuid4()

        await limiter.acquire(agent_id, run_id)

        bus.publish.assert_called_once()
        event_arg = bus.publish.call_args[0][0]
        assert isinstance(event_arg, SlotAcquiredEvent)
        assert event_arg.agent_id == agent_id
        assert event_arg.run_id == run_id

    async def test_release_publishes_slot_released_event(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=2, event_bus=bus)
        agent_id = "agent-1"
        run_id = uuid4()

        await limiter.acquire(agent_id, run_id)
        bus.publish.reset_mock()
        await limiter.release(agent_id, run_id, outcome="done")

        bus.publish.assert_called_once()
        event_arg = bus.publish.call_args[0][0]
        assert isinstance(event_arg, SlotReleasedEvent)
        assert event_arg.agent_id == agent_id
        assert event_arg.run_id == run_id
        assert event_arg.outcome == "done"

    async def test_acquire_decrements_available_slots(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=3, event_bus=bus)

        assert limiter.current_state.active_slots == 0
        await limiter.acquire("a", uuid4())
        assert limiter.current_state.active_slots == 1
        await limiter.acquire("b", uuid4())
        assert limiter.current_state.active_slots == 2

    async def test_release_increments_available_slots(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=2, event_bus=bus)
        run_id = uuid4()

        await limiter.acquire("a", run_id)
        assert limiter.current_state.active_slots == 1
        await limiter.release("a", run_id, outcome="done")
        assert limiter.current_state.active_slots == 0


class TestConcurrencyLimiterSlotCap:
    async def test_third_acquire_blocks_until_release(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=2, event_bus=bus)

        run_ids = [uuid4(), uuid4(), uuid4()]
        await limiter.acquire("a", run_ids[0])
        await limiter.acquire("b", run_ids[1])

        # Third acquire should block — wrap in a task with timeout
        acquired = asyncio.Event()

        async def _third() -> None:
            await limiter.acquire("c", run_ids[2])
            acquired.set()

        task = asyncio.create_task(_third())
        # Give it a moment — should NOT have acquired yet
        await asyncio.sleep(0.05)
        assert not acquired.is_set(), "Third acquire should be blocked"

        # Release one slot
        await limiter.release("a", run_ids[0], outcome="done")
        await asyncio.wait_for(task, timeout=1.0)
        assert acquired.is_set(), "Third acquire should complete after release"

    async def test_max_slots_respected_under_concurrency(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=2, event_bus=bus)
        max_observed = 0
        lock = asyncio.Lock()

        async def _worker(run_id: object) -> None:
            nonlocal max_observed
            await limiter.acquire("agent", run_id)  # type: ignore[arg-type]
            async with lock:
                current = limiter.current_state.active_slots
                if current > max_observed:
                    max_observed = current
            await asyncio.sleep(0.01)
            await limiter.release("agent", run_id, outcome="done")  # type: ignore[arg-type]

        run_ids = [uuid4() for _ in range(5)]
        await asyncio.gather(*[_worker(r) for r in run_ids])
        assert max_observed <= 2


class TestConcurrencyLimiterCurrentState:
    async def test_current_state_returns_correct_values(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=5, event_bus=bus)

        state = limiter.current_state
        assert isinstance(state, ConcurrencyState)
        assert state.max_slots == 5
        assert state.active_slots == 0

    async def test_current_state_reflects_active_count(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=5, event_bus=bus)

        await limiter.acquire("a", uuid4())
        await limiter.acquire("b", uuid4())
        state = limiter.current_state
        assert state.active_slots == 2
        assert state.max_slots == 5


class TestConcurrencyLimiterEventPayloads:
    async def test_slot_acquired_event_has_timestamp(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=2, event_bus=bus)
        before = datetime.now(tz=UTC)
        await limiter.acquire("agent-1", uuid4())
        after = datetime.now(tz=UTC)

        event: SlotAcquiredEvent = bus.publish.call_args[0][0]
        assert before <= event.acquired_at <= after

    async def test_slot_released_event_has_timestamp(self) -> None:
        from lintel.coordination.concurrency_limiter import ConcurrencyLimiter

        bus = AsyncMock()
        limiter = ConcurrencyLimiter(max_slots=2, event_bus=bus)
        run_id = uuid4()
        await limiter.acquire("agent-1", run_id)
        bus.publish.reset_mock()

        before = datetime.now(tz=UTC)
        await limiter.release("agent-1", run_id, outcome="failed")
        after = datetime.now(tz=UTC)

        event: SlotReleasedEvent = bus.publish.call_args[0][0]
        assert before <= event.released_at <= after
        assert event.outcome == "failed"
