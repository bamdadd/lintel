"""Background scheduler loop with advisory lock coordination."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.api.domain.pipeline_scheduler import PipelineScheduler
    from lintel.coordination.advisory_lock import AdvisoryLockCoordinator


class SchedulerLoop:
    """Background task running the pipeline scheduler on a fixed interval."""

    TICK_INTERVAL_SECONDS = 10

    def __init__(
        self,
        coordinator: AdvisoryLockCoordinator,
        scheduler: PipelineScheduler,
    ) -> None:
        self._coordinator = coordinator
        self._scheduler = scheduler

    async def single_tick(self) -> list[str]:
        """Execute a single scheduling tick. Returns list of scheduled run IDs."""
        if not await self._coordinator.try_acquire_scheduler_lock():
            return []
        try:
            return await self._scheduler.tick()
        finally:
            await self._coordinator.release_scheduler_lock()

    async def run(self) -> None:
        """Run the scheduler loop indefinitely."""
        while True:
            await self.single_tick()
            await asyncio.sleep(self.TICK_INTERVAL_SECONDS)
