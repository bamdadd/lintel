"""Cleanup scheduler for sandbox environments after pipeline completion.

Subscribes to pipeline completion events and schedules sandbox cleanup
with configurable retention periods.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from lintel.sandbox.docker_backend import DockerSandboxManager

logger = logging.getLogger(__name__)


class SandboxStoreProtocol(Protocol):
    """Minimal protocol for sandbox metadata persistence."""

    async def list_all(self) -> list[dict[str, Any]]: ...
    async def get(self, sandbox_id: str) -> dict[str, Any] | None: ...
    async def update(self, sandbox_id: str, metadata: dict[str, Any]) -> None: ...
    async def remove(self, sandbox_id: str) -> None: ...


class SandboxCleanupScheduler:
    """Schedules and executes sandbox cleanup after pipeline events.

    Parameters
    ----------
    sandbox_store:
        Metadata store for sandbox records.
    sandbox_manager:
        Docker sandbox manager for destroying containers.
    retention_hours:
        Hours to retain failed-run sandboxes before cleanup (default 24).
    """

    def __init__(
        self,
        sandbox_store: SandboxStoreProtocol,
        sandbox_manager: DockerSandboxManager,
        retention_hours: int = 24,
    ) -> None:
        self._store = sandbox_store
        self._manager = sandbox_manager
        self._retention_hours = retention_hours

    async def on_pipeline_completed(
        self,
        sandbox_id: str,
        *,
        success: bool,
    ) -> None:
        """Schedule cleanup for a sandbox after pipeline completion.

        For successful pipelines, cleanup is immediate.
        For failed pipelines, cleanup is deferred by ``retention_hours``.
        """
        meta = await self._store.get(sandbox_id)
        if meta is None:
            logger.warning("Sandbox %s not found for cleanup scheduling", sandbox_id[:12])
            return

        now = datetime.now(tz=UTC)
        cleanup_at = now if success else now + timedelta(hours=self._retention_hours)

        meta["scheduled_cleanup_at"] = cleanup_at.isoformat()
        await self._store.update(sandbox_id, meta)
        logger.info(
            "Scheduled cleanup for sandbox %s at %s (success=%s)",
            sandbox_id[:12],
            cleanup_at.isoformat(),
            success,
        )

    async def run_due_cleanups(self) -> int:
        """Destroy sandboxes whose scheduled_cleanup_at has passed.

        Returns the number of sandboxes cleaned up.
        """
        now = datetime.now(tz=UTC)
        sandboxes = await self._store.list_all()
        cleaned = 0

        for sb in sandboxes:
            cleanup_at_str = sb.get("scheduled_cleanup_at")
            if not cleanup_at_str:
                continue
            sandbox_id = sb.get("sandbox_id", "")
            if not sandbox_id:
                continue

            try:
                cleanup_at = datetime.fromisoformat(cleanup_at_str)
            except (ValueError, TypeError):
                continue

            if cleanup_at <= now:
                try:
                    await self._manager.destroy(sandbox_id)
                    await self._store.remove(sandbox_id)
                    cleaned += 1
                    logger.info("Cleaned up sandbox %s", sandbox_id[:12])
                except Exception:
                    logger.exception("Failed to clean up sandbox %s", sandbox_id[:12])

        return cleaned
