"""SSE streaming endpoint for real-time run event delivery."""

from __future__ import annotations

import asyncio
import json
import time
from typing import TYPE_CHECKING

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from lintel.api.deps import get_event_store

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from lintel.contracts.events import EventEnvelope

router = APIRouter(prefix="/runs", tags=["streams"])


def _to_sse_event(envelope: EventEnvelope) -> dict[str, object]:
    """Convert an EventEnvelope to an SSE-friendly dict."""
    return {
        "event_type": envelope.event_type,
        "step_id": None,
        "timestamp_ms": int(time.time() * 1000),
        "payload": envelope.payload,
    }


@router.get("/{run_id}/stream")
async def stream_run_events(
    run_id: str,
    request: Request,
) -> StreamingResponse:
    """Stream run events via SSE."""
    event_store = get_event_store(request)

    async def event_generator() -> AsyncGenerator[str]:
        stream_id = f"run:{run_id}"
        last_version = 0
        while True:
            events = await event_store.read_stream(stream_id, from_version=last_version)
            for envelope in events:
                sse_data = _to_sse_event(envelope)
                event_type = str(sse_data["event_type"])
                yield f"event: {event_type}\ndata: {json.dumps(sse_data, default=str)}\n\n"
                last_version += 1
                if event_type in ("PipelineRunCompleted", "PipelineRunFailed"):
                    yield f"event: end\ndata: {json.dumps({'event_type': 'end'})}\n\n"
                    return
            await asyncio.sleep(0.1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
