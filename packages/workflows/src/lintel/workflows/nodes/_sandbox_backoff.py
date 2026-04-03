"""Exponential backoff retry for sandbox pool acquisition."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from lintel.sandbox.protocols import SandboxManager

logger = structlog.get_logger()

DEFAULT_DELAYS: tuple[float, ...] = (30.0, 60.0, 120.0)


class SandboxStoreProtocol(Protocol):
    """Minimal store interface needed for pool acquisition."""

    async def list_all(self) -> list[dict[str, Any]]: ...

    async def get(self, sandbox_id: str) -> dict[str, Any] | None: ...


async def acquire_pool_sandbox(
    sandbox_store: SandboxStoreProtocol,
    sandbox_manager: SandboxManager,
    *,
    delays: tuple[float, ...] = DEFAULT_DELAYS,
    log_fn: Callable[[str], Coroutine[object, object, None]] | None = None,
) -> str:
    """Try to acquire a free sandbox from the pool with exponential backoff.

    Checks the pool for an unallocated sandbox and verifies its container is
    still alive. If no sandbox is available, retries up to ``len(delays)``
    times with the specified delays between attempts.

    Args:
        sandbox_store: Store listing sandbox pool entries.
        sandbox_manager: Manager to verify sandbox liveness.
        delays: Sleep durations (seconds) between retry attempts.
        log_fn: Optional async callable ``(msg: str) -> None`` for progress logs.

    Returns:
        The ``sandbox_id`` of an available, verified sandbox.

    Raises:
        NoSandboxAvailableError: If all attempts are exhausted.
    """
    from lintel.sandbox.errors import NoSandboxAvailableError

    max_attempts = 1 + len(delays)
    for attempt in range(max_attempts):
        existing = await sandbox_store.list_all()
        free = [s for s in existing if not s.get("pipeline_id")]

        if free:
            candidate_id: str = free[0].get("sandbox_id", "")
            if candidate_id:
                try:
                    await sandbox_manager.get_status(candidate_id)
                    logger.info(
                        "sandbox_pool_acquired",
                        sandbox=candidate_id[:12],
                        attempt=attempt + 1,
                        total_attempts=max_attempts,
                    )
                    if log_fn is not None:
                        await log_fn(
                            f"Sandbox acquired ({candidate_id[:12]}) "
                            f"on attempt {attempt + 1}/{max_attempts}"
                        )
                    return candidate_id
                except Exception:
                    logger.warning(
                        "pool_sandbox_stale",
                        sandbox=candidate_id[:12],
                        attempt=attempt + 1,
                    )

        if attempt < len(delays):
            delay = delays[attempt]
            msg = (
                f"No sandbox available (attempt {attempt + 1}/{max_attempts}), "
                f"retrying in {delay:.0f}s..."
            )
            logger.info(
                "sandbox_pool_backoff",
                attempt=attempt + 1,
                total_attempts=max_attempts,
                delay_seconds=delay,
                pool_size=len(existing),
                free_count=len(free),
            )
            if log_fn is not None:
                await log_fn(msg)
            await asyncio.sleep(delay)
        else:
            break

    logger.error(
        "sandbox_pool_exhausted",
        total_attempts=max_attempts,
        delays=delays,
    )
    if log_fn is not None:
        await log_fn(
            f"No sandbox available after {max_attempts} attempts "
            f"(backoff: {', '.join(f'{d:.0f}s' for d in delays)}). "
            "Pre-provision sandboxes or wait for one to be released."
        )
    raise NoSandboxAvailableError
