"""Tests for interrupt timeout scheduler."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock
from uuid import uuid4

from lintel.coordination.interrupt_timeout import check_interrupt_timeouts
from lintel.workflows.repositories.interrupt_repository import InMemoryInterruptRepository
from lintel.workflows.types import InterruptRequest, InterruptType, TimeoutSentinel


def _make_request(
    *,
    deadline: datetime | None = None,
    stage: str = "approval_gate",
) -> InterruptRequest:
    return InterruptRequest(
        id=uuid4(),
        run_id="run-1",
        stage=stage,
        interrupt_type=InterruptType.APPROVAL_GATE,
        payload={},
        timeout_seconds=60,
        deadline=deadline,
    )


class TestCheckInterruptTimeouts:
    async def test_no_expired_returns_zero(self) -> None:
        repo = InMemoryInterruptRepository()
        count = await check_interrupt_timeouts(repo)
        assert count == 0

    async def test_expired_interrupt_marked_timed_out(self) -> None:
        repo = InMemoryInterruptRepository()
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        req = _make_request(deadline=past)
        await repo.create_interrupt(req)

        count = await check_interrupt_timeouts(repo)
        assert count == 1

        record = await repo.get_by_id(req.id)
        assert record is not None
        assert record.status.value == "timed_out"

    async def test_executor_resume_called_with_timeout_sentinel(self) -> None:
        repo = InMemoryInterruptRepository()
        past = datetime.now(tz=UTC) - timedelta(minutes=1)
        req = _make_request(deadline=past)
        await repo.create_interrupt(req)

        executor = AsyncMock()
        executor.resume = AsyncMock()

        await check_interrupt_timeouts(repo, executor=executor)

        executor.resume.assert_called_once()
        call_args = executor.resume.call_args
        assert call_args.args[0] == "run-1"
        assert isinstance(call_args.kwargs["human_input"], TimeoutSentinel)

    async def test_event_published_on_timeout(self) -> None:
        repo = InMemoryInterruptRepository()
        past = datetime.now(tz=UTC) - timedelta(minutes=1)
        req = _make_request(deadline=past)
        await repo.create_interrupt(req)

        event_store = AsyncMock()
        event_store.append = AsyncMock()

        await check_interrupt_timeouts(repo, event_store=event_store)

        event_store.append.assert_called_once()

    async def test_non_expired_not_timed_out(self) -> None:
        repo = InMemoryInterruptRepository()
        future = datetime.now(tz=UTC) + timedelta(hours=1)
        req = _make_request(deadline=future)
        await repo.create_interrupt(req)

        count = await check_interrupt_timeouts(repo)
        assert count == 0
