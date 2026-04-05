"""Sandbox preview endpoints: start, get, and stop preview servers."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.sandbox.errors import SandboxNotFoundError
from lintel.sandbox.events import SandboxPreviewStarted, SandboxPreviewStopped

router = APIRouter()


class StartPreviewRequest(BaseModel):
    command: str = ""
    port: int = 0


@router.post("/sandboxes/{sandbox_id}/preview")
async def start_preview(
    sandbox_id: str,
    body: StartPreviewRequest,
    request: Request,
) -> dict[str, Any]:
    """Start a preview server inside a sandbox.

    Auto-detects the app framework if command/port are not specified.
    Returns the preview URL and status.
    """
    manager = request.app.state.sandbox_manager
    try:
        info = await manager.start_preview(
            sandbox_id,
            command=body.command,
            port=body.port,
        )
        result: dict[str, Any] = {
            "sandbox_id": info.sandbox_id,
            "status": info.status.value,
            "preview_url": info.preview_url,
            "container_port": info.container_port,
            "host_port": info.host_port,
            "framework": info.framework,
        }
        if info.started_at is not None:
            result["started_at"] = info.started_at.isoformat()

        if info.status.value == "running":
            await dispatch_event(
                request,
                SandboxPreviewStarted(
                    payload={
                        "resource_id": sandbox_id,
                        "preview_url": info.preview_url,
                        "framework": info.framework,
                        "port": info.container_port,
                    },
                ),
                stream_id=f"sandbox:{sandbox_id}",
            )
        return result
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.get("/sandboxes/{sandbox_id}/preview")
async def get_preview(
    sandbox_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get the current preview status for a sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        info = await manager.get_preview(sandbox_id)
        result: dict[str, Any] = {
            "sandbox_id": info.sandbox_id,
            "status": info.status.value,
            "preview_url": info.preview_url,
            "container_port": info.container_port,
            "host_port": info.host_port,
            "framework": info.framework,
        }
        if info.started_at is not None:
            result["started_at"] = info.started_at.isoformat()
        return result
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.delete("/sandboxes/{sandbox_id}/preview", status_code=204)
async def stop_preview(
    sandbox_id: str,
    request: Request,
) -> None:
    """Stop the preview server running inside a sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        await manager.stop_preview(sandbox_id)
        await dispatch_event(
            request,
            SandboxPreviewStopped(
                payload={"resource_id": sandbox_id},
            ),
            stream_id=f"sandbox:{sandbox_id}",
        )
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None
