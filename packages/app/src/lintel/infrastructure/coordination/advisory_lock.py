"""PostgreSQL advisory lock coordinator for single-scheduler-per-tick."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import asyncpg


class AdvisoryLockCoordinator:
    """PostgreSQL advisory locks for single-scheduler-per-tick coordination."""

    SCHEDULER_LOCK_ID = 42424242

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def try_acquire_scheduler_lock(self) -> bool:
        """Non-blocking attempt to acquire the scheduler advisory lock."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            result = await conn.fetchval(
                "SELECT pg_try_advisory_lock($1)",
                self.SCHEDULER_LOCK_ID,
            )
            return bool(result)

    async def release_scheduler_lock(self) -> None:
        """Release the scheduler advisory lock."""
        async with self._pool.acquire() as conn:  # type: ignore[no-untyped-call]
            await conn.execute(
                "SELECT pg_advisory_unlock($1)",
                self.SCHEDULER_LOCK_ID,
            )
