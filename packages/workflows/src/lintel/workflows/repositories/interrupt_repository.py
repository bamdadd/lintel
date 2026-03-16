"""Interrupt persistence repository.

Provides an in-memory implementation following the same store pattern
used by other packages.  A Postgres-backed implementation can replace
this at app startup via StoreProvider.override().
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from uuid import UUID

from lintel.workflows.types import (
    InterruptRecord,
    InterruptRequest,
    InterruptStatus,
)


class InterruptRepository(Protocol):
    """Protocol for interrupt persistence."""

    async def create_interrupt(self, request: InterruptRequest) -> InterruptRecord: ...

    async def get_interrupt(self, run_id: str, stage: str) -> InterruptRecord | None: ...

    async def get_by_id(self, interrupt_id: UUID) -> InterruptRecord | None: ...

    async def get_pending_past_deadline(self, now: datetime) -> list[InterruptRecord]: ...

    async def mark_resumed(
        self,
        interrupt_id: UUID,
        resumed_by: str,
        resume_input: dict[str, Any] | None = None,
    ) -> InterruptRecord: ...

    async def mark_timed_out(self, interrupt_id: UUID) -> InterruptRecord: ...


class InMemoryInterruptRepository:
    """In-memory implementation of InterruptRepository."""

    def __init__(self) -> None:
        self._records: dict[UUID, InterruptRecord] = {}

    async def create_interrupt(self, request: InterruptRequest) -> InterruptRecord:
        now = datetime.now(tz=UTC)
        record = InterruptRecord(
            id=request.id,
            run_id=request.run_id,
            stage=request.stage,
            interrupt_type=request.interrupt_type,
            payload=request.payload,
            status=InterruptStatus.PENDING,
            deadline=request.deadline,
            created_at=now,
            updated_at=now,
        )
        self._records[record.id] = record
        return record

    async def get_interrupt(self, run_id: str, stage: str) -> InterruptRecord | None:
        for record in reversed(list(self._records.values())):
            if record.run_id == run_id and record.stage == stage:
                return record
        return None

    async def get_by_id(self, interrupt_id: UUID) -> InterruptRecord | None:
        return self._records.get(interrupt_id)

    async def get_pending_past_deadline(self, now: datetime) -> list[InterruptRecord]:
        results: list[InterruptRecord] = []
        for record in self._records.values():
            if (
                record.status == InterruptStatus.PENDING
                and record.deadline is not None
                and record.deadline <= now
            ):
                results.append(record)
        return results

    async def mark_resumed(
        self,
        interrupt_id: UUID,
        resumed_by: str,
        resume_input: dict[str, Any] | None = None,
    ) -> InterruptRecord:
        record = self._records[interrupt_id]
        updated = replace(
            record,
            status=InterruptStatus.RESUMED,
            resumed_by=resumed_by,
            resume_input=resume_input,
            updated_at=datetime.now(tz=UTC),
        )
        self._records[interrupt_id] = updated
        return updated

    async def mark_timed_out(self, interrupt_id: UUID) -> InterruptRecord:
        record = self._records[interrupt_id]
        updated = replace(
            record,
            status=InterruptStatus.TIMED_OUT,
            updated_at=datetime.now(tz=UTC),
        )
        self._records[interrupt_id] = updated
        return updated
