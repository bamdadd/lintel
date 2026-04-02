"""Image rebuild scheduler — evaluates cron schedules and tracks due builds."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from croniter import croniter  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from lintel.domain.types import ImageBuildSchedule
    from lintel.sandbox_pool_api.store import InMemoryImageBuildScheduleStore


class ImageRebuildScheduler:
    """Evaluates image build schedules and returns which are due for rebuild."""

    def __init__(self, schedule_store: InMemoryImageBuildScheduleStore) -> None:
        self._store = schedule_store
        self._last_check: dict[str, datetime] = {}

    async def get_due_schedules(
        self,
        now: datetime | None = None,
    ) -> list[ImageBuildSchedule]:
        """Return schedules that are due for a rebuild."""
        now = now or datetime.now(UTC)
        enabled = await self._store.list_enabled()
        due: list[ImageBuildSchedule] = []
        for sched in enabled:
            if self._is_due(sched, now):
                due.append(sched)
        return due

    def _is_due(self, schedule: ImageBuildSchedule, now: datetime) -> bool:
        """Check if a schedule is due based on its cron expression."""
        last_check = self._last_check.get(schedule.schedule_id)
        if last_check is None:
            # First check — use last_built_at or created_at as baseline
            baseline = schedule.last_built_at or schedule.created_at
        else:
            baseline = last_check

        cron = croniter(schedule.cron_expression, baseline)
        next_fire: datetime = cron.get_next(datetime)
        if next_fire.tzinfo is None:
            next_fire = next_fire.replace(tzinfo=UTC)

        if next_fire <= now:
            self._last_check[schedule.schedule_id] = now
            return True
        return False

    async def mark_built(
        self,
        schedule_id: str,
        commit_sha: str = "",
    ) -> None:
        """Update a schedule after a successful build."""
        now = datetime.now(UTC)
        await self._store.update(
            schedule_id,
            {"last_built_at": now, "last_commit_sha": commit_sha},
        )
        self._last_check[schedule_id] = now
