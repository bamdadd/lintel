"""Tests for InMemoryInterruptRepository."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from lintel.workflows.repositories.interrupt_repository import InMemoryInterruptRepository
from lintel.workflows.types import InterruptRequest, InterruptStatus, InterruptType


def _make_request(
    *,
    timeout_seconds: int = 0,
    deadline: datetime | None = None,
) -> InterruptRequest:
    return InterruptRequest(
        id=uuid4(),
        run_id="run-1",
        stage="approval_gate_spec",
        interrupt_type=InterruptType.APPROVAL_GATE,
        payload={"node_name": "approval_gate_spec"},
        timeout_seconds=timeout_seconds,
        deadline=deadline,
    )


class TestInMemoryInterruptRepository:
    async def test_create_and_get(self) -> None:
        repo = InMemoryInterruptRepository()
        req = _make_request()
        record = await repo.create_interrupt(req)

        assert record.run_id == "run-1"
        assert record.stage == "approval_gate_spec"
        assert record.status == InterruptStatus.PENDING

        fetched = await repo.get_interrupt("run-1", "approval_gate_spec")
        assert fetched is not None
        assert fetched.id == record.id

    async def test_get_by_id(self) -> None:
        repo = InMemoryInterruptRepository()
        req = _make_request()
        record = await repo.create_interrupt(req)

        fetched = await repo.get_by_id(record.id)
        assert fetched is not None
        assert fetched.stage == "approval_gate_spec"

    async def test_get_nonexistent_returns_none(self) -> None:
        repo = InMemoryInterruptRepository()
        assert await repo.get_interrupt("no-run", "no-stage") is None
        assert await repo.get_by_id(uuid4()) is None

    async def test_mark_resumed(self) -> None:
        repo = InMemoryInterruptRepository()
        req = _make_request()
        record = await repo.create_interrupt(req)

        updated = await repo.mark_resumed(record.id, "user-1", {"input": "approved"})
        assert updated.status == InterruptStatus.RESUMED
        assert updated.resumed_by == "user-1"
        assert updated.resume_input == {"input": "approved"}

    async def test_mark_timed_out(self) -> None:
        repo = InMemoryInterruptRepository()
        req = _make_request()
        record = await repo.create_interrupt(req)

        updated = await repo.mark_timed_out(record.id)
        assert updated.status == InterruptStatus.TIMED_OUT

    async def test_get_pending_past_deadline(self) -> None:
        repo = InMemoryInterruptRepository()
        past = datetime.now(tz=UTC) - timedelta(minutes=5)
        future = datetime.now(tz=UTC) + timedelta(hours=1)

        req_expired = _make_request(timeout_seconds=60, deadline=past)
        req_active = _make_request(timeout_seconds=3600, deadline=future)

        await repo.create_interrupt(req_expired)
        await repo.create_interrupt(req_active)

        expired = await repo.get_pending_past_deadline(datetime.now(tz=UTC))
        assert len(expired) == 1
        assert expired[0].id == req_expired.id

    async def test_get_pending_past_deadline_excludes_resumed(self) -> None:
        repo = InMemoryInterruptRepository()
        past = datetime.now(tz=UTC) - timedelta(minutes=5)

        req = _make_request(timeout_seconds=60, deadline=past)
        record = await repo.create_interrupt(req)
        await repo.mark_resumed(record.id, "user")

        expired = await repo.get_pending_past_deadline(datetime.now(tz=UTC))
        assert len(expired) == 0
