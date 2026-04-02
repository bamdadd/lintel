"""Background scheduler for automatic sandbox image rebuilds."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
import logging
from typing import Any
from uuid import uuid4

from lintel.domain.types import (
    ImageRebuildRecord,
    ImageRebuildStatus,
    SandboxImage,
)
from lintel.sandbox_pool_api.store import (  # noqa: TC001
    InMemoryImageRebuildStore,
    InMemorySandboxImageStore,
    InMemorySandboxPoolConfigStore,
)

logger = logging.getLogger(__name__)


class ImageRebuildScheduler:
    """Periodically checks pool configs and triggers image rebuilds when due."""

    def __init__(
        self,
        config_store: InMemorySandboxPoolConfigStore,
        image_store: InMemorySandboxImageStore,
        rebuild_store: InMemoryImageRebuildStore,
        *,
        check_interval_seconds: int = 60,
    ) -> None:
        self._config_store = config_store
        self._image_store = image_store
        self._rebuild_store = rebuild_store
        self._check_interval = check_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background scheduler loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Image rebuild scheduler started (interval=%ds)", self._check_interval)

    async def stop(self) -> None:
        """Stop the background scheduler loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("Image rebuild scheduler stopped")

    async def _run_loop(self) -> None:
        while self._running:
            try:
                await self._check_and_rebuild()
            except Exception:
                logger.exception("Error in image rebuild scheduler loop")
            await asyncio.sleep(self._check_interval)

    async def _check_and_rebuild(self) -> None:
        """Check all project configs and trigger rebuilds where due."""
        configs = self._config_store._items.values()
        now = datetime.now(UTC)

        for config in list(configs):
            interval = config.rebuild_interval_seconds
            if interval <= 0:
                continue

            latest = await self._rebuild_store.latest_for_project(config.project_id)
            if latest is not None:
                last_started = datetime.fromisoformat(latest["started_at"])
                elapsed = (now - last_started).total_seconds()
                if elapsed < interval:
                    continue

            await self.trigger_rebuild(config.project_id, trigger="scheduled")

    async def trigger_rebuild(
        self,
        project_id: str,
        *,
        trigger: str = "manual",
        commit_sha: str = "",
        branch: str = "main",
    ) -> dict[str, Any]:
        """Create a rebuild record and simulate building a new image."""
        now = datetime.now(UTC)
        rebuild_id = str(uuid4())

        record = ImageRebuildRecord(
            rebuild_id=rebuild_id,
            image_id="",
            project_id=project_id,
            trigger=trigger,
            status=ImageRebuildStatus.BUILDING,
            commit_sha=commit_sha,
            branch=branch,
            started_at=now,
        )
        await self._rebuild_store.add(record)

        image_id = str(uuid4())
        image = SandboxImage(
            image_id=image_id,
            repository_url=f"project:{project_id}",
            branch=branch,
            commit_sha=commit_sha,
            image_tag=f"rebuild-{rebuild_id[:8]}",
            created_at=now,
        )
        await self._image_store.add(image)

        completed_at = datetime.now(UTC)
        await self._rebuild_store.update(
            rebuild_id,
            {
                "image_id": image_id,
                "status": ImageRebuildStatus.COMPLETED,
                "completed_at": completed_at,
            },
        )

        logger.info(
            "Image rebuild completed: project=%s rebuild=%s image=%s",
            project_id,
            rebuild_id,
            image_id,
        )

        result = await self._rebuild_store.get(rebuild_id)
        assert result is not None
        return result
