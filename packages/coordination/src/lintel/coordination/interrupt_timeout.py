"""Interrupt timeout scheduler.

Periodically checks for pending interrupts past their deadline and
resumes the graph with a TimeoutSentinel, then marks them timed out.

Wire into the application's background task scheduler to run every 30 seconds.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from lintel.workflows.repositories.interrupt_repository import InterruptRepository

logger = structlog.get_logger()


async def check_interrupt_timeouts(
    interrupt_repository: InterruptRepository,
    event_store: Any = None,  # noqa: ANN401
    executor: Any = None,  # noqa: ANN401
) -> int:
    """Check for expired interrupts and trigger timeouts.

    Returns the number of interrupts that were timed out.

    Parameters
    ----------
    interrupt_repository:
        The interrupt store to query and update.
    event_store:
        Optional event store for publishing HumanInterruptTimedOut events.
    executor:
        Optional workflow executor for resuming graphs with TimeoutSentinel.
    """
    now = datetime.now(tz=UTC)
    expired = await interrupt_repository.get_pending_past_deadline(now)

    if not expired:
        return 0

    timed_out = 0
    for record in expired:
        try:
            # Resume graph with TimeoutSentinel if executor is available
            if executor is not None and hasattr(executor, "resume"):
                try:
                    from lintel.workflows.types import TimeoutSentinel

                    sentinel = TimeoutSentinel(
                        reason=f"Deadline passed for {record.stage}",
                    )
                    await executor.resume(record.run_id, human_input=sentinel)
                except Exception:
                    logger.warning(
                        "timeout_resume_failed",
                        run_id=record.run_id,
                        stage=record.stage,
                    )

            # Mark as timed out
            await interrupt_repository.mark_timed_out(record.id)
            timed_out += 1

            # Publish event
            if event_store is not None:
                try:
                    from lintel.workflows.events import HumanInterruptTimedOut

                    event = HumanInterruptTimedOut(
                        payload={
                            "interrupt_id": str(record.id),
                            "run_id": record.run_id,
                            "stage": record.stage,
                            "interrupt_type": record.interrupt_type.value,
                            "deadline": record.deadline.isoformat() if record.deadline else None,
                        },
                    )
                    await event_store.append(
                        stream_id=f"run:{record.run_id}",
                        events=[event],
                    )
                except Exception:
                    logger.warning(
                        "timeout_event_publish_failed",
                        run_id=record.run_id,
                    )

            logger.info(
                "interrupt_timed_out",
                interrupt_id=str(record.id),
                run_id=record.run_id,
                stage=record.stage,
            )
        except Exception:
            logger.warning(
                "timeout_processing_failed",
                interrupt_id=str(record.id),
                exc_info=True,
            )

    return timed_out
