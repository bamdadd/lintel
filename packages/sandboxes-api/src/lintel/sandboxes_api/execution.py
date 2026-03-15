"""Sandbox execution endpoints: execute command, get logs."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.sandbox.errors import SandboxNotFoundError
from lintel.sandbox.events import SandboxCommandExecuted
from lintel.sandbox.types import SandboxJob

router = APIRouter()


class ExecuteRequest(BaseModel):
    command: str
    workdir: str | None = None
    timeout_seconds: int = 300


@router.post("/sandboxes/{sandbox_id}/execute")
async def execute_command(
    sandbox_id: str,
    body: ExecuteRequest,
    request: Request,
) -> dict[str, Any]:
    """Execute a command in a sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        result = await manager.execute(
            sandbox_id,
            SandboxJob(
                command=body.command,
                workdir=body.workdir,
                timeout_seconds=body.timeout_seconds,
            ),
        )
        await dispatch_event(
            request,
            SandboxCommandExecuted(
                payload={"resource_id": sandbox_id, "command": body.command[:200]}
            ),
            stream_id=f"sandbox:{sandbox_id}",
        )
        return {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.get("/sandboxes/{sandbox_id}/logs")
async def get_sandbox_logs(
    sandbox_id: str,
    request: Request,
    tail: int = 200,
) -> dict[str, Any]:
    """Get container logs for a sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        logs = await manager.get_logs(sandbox_id, tail=tail)
        return {"sandbox_id": sandbox_id, "logs": logs}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None
