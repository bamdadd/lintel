"""Sandbox management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.errors import SandboxNotFoundError
from lintel.contracts.types import SandboxConfig, SandboxJob, ThreadRef

router = APIRouter()


class CreateSandboxRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    image: str = "python:3.12-slim"
    network_enabled: bool = False


class ExecuteRequest(BaseModel):
    command: str
    workdir: str | None = None
    timeout_seconds: int = 300


class WriteFileRequest(BaseModel):
    path: str
    content: str


@router.post("/sandboxes", status_code=201)
async def create_sandbox(
    body: CreateSandboxRequest,
    request: Request,
) -> dict[str, str]:
    """Create a new sandbox environment."""
    manager = request.app.state.sandbox_manager
    config = SandboxConfig(image=body.image, network_enabled=body.network_enabled)
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    sandbox_id = await manager.create(config, thread_ref)
    return {"sandbox_id": sandbox_id}


@router.get("/sandboxes/{sandbox_id}")
async def get_sandbox_status(
    sandbox_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get sandbox status."""
    manager = request.app.state.sandbox_manager
    try:
        status = await manager.get_status(sandbox_id)
        return {"sandbox_id": sandbox_id, "status": status.value}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


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
        return {
            "exit_code": result.exit_code,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.post("/sandboxes/{sandbox_id}/files")
async def write_file(
    sandbox_id: str,
    body: WriteFileRequest,
    request: Request,
) -> dict[str, str]:
    """Write a file to the sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        await manager.write_file(sandbox_id, body.path, body.content)
        return {"status": "written", "path": body.path}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.get("/sandboxes/{sandbox_id}/files")
async def read_file(
    sandbox_id: str,
    path: str,
    request: Request,
) -> dict[str, str]:
    """Read a file from the sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        content = await manager.read_file(sandbox_id, path)
        return {"path": path, "content": content}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.delete("/sandboxes/{sandbox_id}", status_code=204)
async def destroy_sandbox(sandbox_id: str, request: Request) -> None:
    """Destroy a sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        await manager.destroy(sandbox_id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None
