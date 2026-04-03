"""Zombie run reaper — periodic cleanup of stale pipeline runs.

Marks queued/pending runs older than a threshold as cancelled, and
running runs older than a threshold as failed with a reaper error.
"""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime
import logging
from typing import TYPE_CHECKING

from lintel.workflows.types import PipelineRun, PipelineStatus, StageStatus

if TYPE_CHECKING:
    from lintel.pipelines_api._store import InMemoryPipelineStore

logger = logging.getLogger(__name__)

_STALE_QUEUED = {PipelineStatus.QUEUED, PipelineStatus.PENDING}
_STALE_RUNNING = {PipelineStatus.RUNNING}
_ACTIVE_STAGE = {StageStatus.RUNNING, StageStatus.PENDING}

DEFAULT_QUEUED_MAX_AGE = 3600  # 1 hour
DEFAULT_RUNNING_MAX_AGE = 7200  # 2 hours
DEFAULT_INTERVAL = 300  # 5 minutes


class ZombieRunReaper:
    """Reaps zombie pipeline runs that are stuck in non-terminal states."""

    def __init__(self, store: InMemoryPipelineStore) -> None:
        self._store = store
        self._task: asyncio.Task[None] | None = None

    async def reap_stale_queued(
        self,
        max_age_seconds: int = DEFAULT_QUEUED_MAX_AGE,
    ) -> int:
        """Cancel queued/pending runs older than max_age_seconds."""
        runs = await self._store.list_all()
        now = datetime.now(UTC)
        count = 0

        for run in runs:
            if run.status not in _STALE_QUEUED:
                continue
            age = _age_seconds(run, now)
            if age is None or age < max_age_seconds:
                continue

            updated = replace(run, status=PipelineStatus.CANCELLED)
            await self._store.update(updated)
            count += 1
            logger.info("reaper.cancelled_stale_queued", extra={"run_id": run.run_id, "age_s": age})

        return count

    async def reap_stale_running(
        self,
        max_age_seconds: int = DEFAULT_RUNNING_MAX_AGE,
    ) -> int:
        """Fail running runs older than max_age_seconds, marking active stages as failed."""
        runs = await self._store.list_all()
        now = datetime.now(UTC)
        count = 0

        for run in runs:
            if run.status not in _STALE_RUNNING:
                continue
            age = _age_seconds(run, now)
            if age is None or age < max_age_seconds:
                continue

            failed_stages = tuple(
                replace(
                    s,
                    status=StageStatus.FAILED,
                    error="Terminated by zombie reaper: run exceeded maximum age",
                )
                if s.status in _ACTIVE_STAGE
                else s
                for s in run.stages
            )
            updated = replace(run, status=PipelineStatus.FAILED, stages=failed_stages)
            await self._store.update(updated)
            count += 1
            logger.info("reaper.failed_stale_running", extra={"run_id": run.run_id, "age_s": age})

        return count

    async def reap(
        self,
        queued_max_age: int = DEFAULT_QUEUED_MAX_AGE,
        running_max_age: int = DEFAULT_RUNNING_MAX_AGE,
    ) -> int:
        """Run all reaper sweeps. Returns total number of reaped runs."""
        total = 0
        total += await self.reap_stale_queued(max_age_seconds=queued_max_age)
        total += await self.reap_stale_running(max_age_seconds=running_max_age)
        if total > 0:
            logger.info("reaper.sweep_complete", extra={"reaped": total})
        return total

    async def start_periodic(self, interval_seconds: int = DEFAULT_INTERVAL) -> None:
        """Start a background task that runs reap() on a fixed interval."""
        await self.stop()
        self._task = asyncio.create_task(self._loop(interval_seconds))

    async def stop(self) -> None:
        """Cancel the periodic reaper task if running."""
        if self._task is not None and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _loop(self, interval: int) -> None:
        """Internal loop — runs reap() then sleeps."""
        while True:
            try:
                await self.reap()
            except Exception:
                logger.exception("reaper.sweep_error")
            await asyncio.sleep(interval)


def _age_seconds(run: PipelineRun, now: datetime) -> float | None:
    """Compute the age of a run in seconds, or None if created_at is missing/invalid."""
    if not run.created_at:
        return None
    try:
        created = datetime.fromisoformat(run.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return (now - created).total_seconds()
    except (ValueError, TypeError):
        return None
