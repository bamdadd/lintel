"""Background task that periodically checks sandbox storage usage.

The monitor polls each active sandbox at a configurable interval,
persisting usage data and logging warnings when limits are approached.
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime
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


class SandboxStorageMonitor:
    """Polls active sandboxes for disk usage and persists the results.

    Parameters
    ----------
    sandbox_store:
        Metadata store for sandbox records.
    sandbox_manager:
        Docker sandbox manager with ``get_storage_usage`` method.
    poll_interval_seconds:
        Seconds between polling cycles (default 300 = 5 minutes).
    """

    def __init__(
        self,
        sandbox_store: SandboxStoreProtocol,
        sandbox_manager: DockerSandboxManager,
        poll_interval_seconds: float = 300.0,
    ) -> None:
        self._store = sandbox_store
        self._manager = sandbox_manager
        self._poll_interval = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running = False

    async def start(self) -> None:
        """Start the background polling loop."""
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("SandboxStorageMonitor started (interval=%ss)", self._poll_interval)

    async def stop(self) -> None:
        """Stop the background polling loop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        logger.info("SandboxStorageMonitor stopped")

    async def _poll_loop(self) -> None:
        """Main polling loop — runs until cancelled."""
        while self._running:
            try:
                await self._check_all_sandboxes()
            except Exception:
                logger.exception("Storage monitor poll failed")
            await asyncio.sleep(self._poll_interval)

    async def _check_all_sandboxes(self) -> None:
        """Check storage usage for every active sandbox."""
        sandboxes = await self._store.list_all()
        for sb in sandboxes:
            sandbox_id = sb.get("sandbox_id", "")
            if not sandbox_id:
                continue
            status = sb.get("status", "")
            if status in ("destroyed", "failed", "completed"):
                continue
            await self._check_one(sandbox_id, sb)

    async def _check_one(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        """Check storage for a single sandbox and persist the result."""
        try:
            usage_bytes = await self._manager.get_storage_usage(sandbox_id)
        except Exception:
            logger.warning("Failed to get storage usage for %s", sandbox_id[:12])
            return

        now = datetime.now(tz=UTC).isoformat()
        metadata["storage_usage_bytes"] = usage_bytes
        metadata["storage_checked_at"] = now
        await self._store.update(sandbox_id, metadata)

        limit_gb = metadata.get("storage_limit_gb", 4)
        limit_bytes = limit_gb * 1024 * 1024 * 1024
        if usage_bytes > limit_bytes:
            logger.warning(
                "Sandbox %s exceeds storage limit: %d bytes used, %d bytes limit",
                sandbox_id[:12],
                usage_bytes,
                limit_bytes,
            )
        elif usage_bytes > limit_bytes * 0.9:
            logger.warning(
                "Sandbox %s approaching storage limit: %d/%d bytes (%.0f%%)",
                sandbox_id[:12],
                usage_bytes,
                limit_bytes,
                usage_bytes / limit_bytes * 100,
            )
