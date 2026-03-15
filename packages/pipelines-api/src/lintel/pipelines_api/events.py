"""SSE streaming route handlers: stream_pipeline_events, stream_stage_logs."""

import asyncio
from collections.abc import AsyncGenerator
import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from lintel.pipelines_api._helpers import _find_stage
from lintel.pipelines_api._store import InMemoryPipelineStore, pipeline_store_provider

router = APIRouter()


@router.get("/pipelines/{run_id}/stages/{stage_id}/logs")
async def stream_stage_logs(
    run_id: str,
    stage_id: str,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> StreamingResponse:
    """Stream stage logs via SSE. Shows stored logs and polls for new ones."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    stage = _find_stage(run, stage_id)
    if stage is None:
        raise HTTPException(status_code=404, detail="Stage not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        last_log_count = 0
        last_status = ""
        while True:
            run = await store.get(run_id)
            if run is None:
                return
            stage = _find_stage(run, stage_id)
            if stage is None:
                return

            # Emit any new log lines
            current_logs = list(stage.logs) if stage.logs else []
            if len(current_logs) > last_log_count:
                for line in current_logs[last_log_count:]:
                    yield f"data: {json.dumps({'type': 'log', 'line': line})}\n\n"
                last_log_count = len(current_logs)

            # Emit status changes
            status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
            if status != last_status:
                last_status = status
                yield f"data: {json.dumps({'type': 'status', 'status': status})}\n\n"

            # Emit outputs and error for completed/failed stages
            if status in ("succeeded", "failed", "skipped"):
                if stage.outputs:
                    payload = json.dumps(
                        {"type": "outputs", "data": stage.outputs},
                        default=str,
                    )
                    yield f"data: {payload}\n\n"
                if stage.error:
                    yield f"data: {json.dumps({'type': 'error', 'message': stage.error})}\n\n"
                yield f"data: {json.dumps({'type': 'end'})}\n\n"
                return

            await asyncio.sleep(0.5)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/pipelines/{run_id}/events")
async def stream_pipeline_events(
    run_id: str,
    store: InMemoryPipelineStore = Depends(pipeline_store_provider),  # noqa: B008
) -> StreamingResponse:
    """Stream pipeline stage status changes via SSE for real-time UI updates."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Pipeline run not found")

    async def event_stream() -> AsyncGenerator[str, None]:
        last_statuses: dict[str, str] = {}
        last_pipeline_status = ""
        while True:
            run = await store.get(run_id)
            if run is None:
                return

            # Emit stage status changes
            for stage in run.stages:
                status = stage.status.value if hasattr(stage.status, "value") else str(stage.status)
                prev = last_statuses.get(stage.stage_id)
                if status != prev:
                    last_statuses[stage.stage_id] = status
                    payload = {
                        "type": "stage_update",
                        "stage_id": stage.stage_id,
                        "name": stage.name,
                        "status": status,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            # Emit pipeline-level status changes
            p_status = run.status.value if hasattr(run.status, "value") else str(run.status)
            if p_status != last_pipeline_status:
                last_pipeline_status = p_status
                yield f"data: {json.dumps({'type': 'pipeline_status', 'status': p_status})}\n\n"

            # End stream when pipeline reaches a terminal state
            if p_status in ("succeeded", "failed", "cancelled"):
                yield f"data: {json.dumps({'type': 'pipeline_complete', 'status': p_status})}\n\n"
                return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
