"""Background task scheduler for periodic coordination tasks.

Provides an asyncio-based scheduler that runs periodic tasks such as
interrupt timeout checking.  Wire into the application lifespan to
start/stop the scheduler.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.workflows.repositories.interrupt_repository import InterruptRepository

logger = structlog.get_logger()

DEFAULT_TIMEOUT_CHECK_INTERVAL_SECONDS = 30


class InterruptTimeoutScheduler:
    """Periodic scheduler for interrupt timeout checks.

    Parameters
    ----------
    interrupt_repository:
        Repository for querying/updating interrupt records.
    event_store:
        Optional event store for publishing timeout events.
    executor:
        Optional workflow executor for resuming graphs.
    interval_seconds:
        How often to check for expired interrupts (default: 30).
    """

    def __init__(
        self,
        interrupt_repository: InterruptRepository,
        event_store: Any = None,  # noqa: ANN401
        executor: Any = None,  # noqa: ANN401
        interval_seconds: int = DEFAULT_TIMEOUT_CHECK_INTERVAL_SECONDS,
    ) -> None:
        self._repo = interrupt_repository
        self._event_store = event_store
        self._executor = executor
        self._interval = interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the periodic timeout checker as a background task."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info(
            "interrupt_timeout_scheduler_started",
            interval_seconds=self._interval,
        )

    async def stop(self) -> None:
        """Stop the periodic timeout checker."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("interrupt_timeout_scheduler_stopped")

    async def _loop(self) -> None:
        """Run the timeout check on a periodic interval."""
        while self._running:
            try:
                from lintel.coordination.interrupt_timeout import (
                    check_interrupt_timeouts,
                )

                count = await check_interrupt_timeouts(
                    self._repo,
                    event_store=self._event_store,
                    executor=self._executor,
                )
                if count > 0:
                    logger.info("interrupt_timeouts_processed", count=count)
            except Exception:
                logger.warning(
                    "interrupt_timeout_check_failed",
                    exc_info=True,
                )

            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
