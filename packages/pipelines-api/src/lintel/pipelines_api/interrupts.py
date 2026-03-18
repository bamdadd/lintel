"""Interrupt resume and query routes for human-in-the-loop workflows.

POST /pipelines/{run_id}/stages/{stage}/resume — resume a paused interrupt
GET  /pipelines/{run_id}/stages/{stage}/interrupt — query interrupt state
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.workflows.events import HumanInterruptResumed
from lintel.workflows.types import InterruptStatus

if TYPE_CHECKING:
    from lintel.workflows.repositories.interrupt_repository import (
        InterruptRepository,
    )

router = APIRouter()

interrupt_store_provider: StoreProvider[InterruptRepository] = StoreProvider()


class ResumeRequest(BaseModel):
    """Body for resuming a paused human interrupt."""

    input: Any = Field(default=None, description="Human-supplied input")
    resumed_by: str = Field(default="user", description="Who resumed the interrupt")


@router.post("/pipelines/{run_id}/stages/{stage}/resume")
async def resume_interrupt(
    run_id: str,
    stage: str,
    body: ResumeRequest,
    request: Request,
    store: InterruptRepository = Depends(interrupt_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Resume a paused workflow interrupt with human input."""
    record = await store.get_interrupt(run_id, stage)
    if record is None:
        raise HTTPException(status_code=404, detail="No interrupt found for this run/stage")

    if record.status != InterruptStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Interrupt is not pending (status={record.status})",
        )

    if record.deadline is not None and record.deadline <= datetime.now(tz=UTC):
        raise HTTPException(status_code=410, detail="Interrupt deadline has passed")

    # Mark as resumed in repository
    updated = await store.mark_resumed(
        record.id,
        resumed_by=body.resumed_by,
        resume_input={"input": body.input} if body.input is not None else None,
    )

    # Resume the graph via workflow executor
    executor = getattr(request.app.state, "workflow_executor", None)
    if executor is not None:
        import asyncio

        try:
            # Use the executor's graph to resume with Command
            task = asyncio.create_task(
                _resume_graph(executor, run_id, body.input),
            )
            bg: set[asyncio.Task[None]] = getattr(request.app.state, "_background_tasks", set())
            request.app.state._background_tasks = bg
            bg.add(task)
            task.add_done_callback(bg.discard)
        except Exception:
            pass  # Best-effort resume; the graph may not be available

    # Publish event
    await dispatch_event(
        request,
        HumanInterruptResumed(
            payload={
                "interrupt_id": str(record.id),
                "run_id": run_id,
                "stage": stage,
                "interrupt_type": record.interrupt_type.value,
                "resumed_by": body.resumed_by,
            },
        ),
        stream_id=f"run:{run_id}",
    )

    return asdict(updated)


@router.get("/pipelines/{run_id}/stages/{stage}/interrupt")
async def get_interrupt(
    run_id: str,
    stage: str,
    store: InterruptRepository = Depends(interrupt_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Query the current interrupt state for a run/stage."""
    record = await store.get_interrupt(run_id, stage)
    if record is None:
        raise HTTPException(status_code=404, detail="No interrupt found for this run/stage")
    return asdict(record)


async def _resume_graph(
    executor: Any,  # noqa: ANN401
    run_id: str,
    human_input: Any,  # noqa: ANN401
) -> None:
    """Helper to resume the graph via the workflow executor."""
    try:
        if hasattr(executor, "resume"):
            await executor.resume(run_id, human_input=human_input)
    except Exception:
        import structlog

        structlog.get_logger().warning(
            "interrupt_resume_graph_failed",
            run_id=run_id,
        )
