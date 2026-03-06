"""Sandbox job endpoints."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.commands import ScheduleSandboxJob
from lintel.contracts.types import AgentRole, SandboxStatus, ThreadRef

router = APIRouter()


def get_sandbox_registry(request: Request) -> dict[str, dict[str, Any]]:
    """Get sandbox registry from app state."""
    if not hasattr(request.app.state, "sandbox_registry"):
        request.app.state.sandbox_registry = {}
    return request.app.state.sandbox_registry  # type: ignore[no-any-return]


class ScheduleSandboxJobRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    agent_role: AgentRole
    repo_url: str
    base_sha: str
    commands: list[str]


@router.post("/sandboxes", status_code=201)
async def schedule_sandbox_job(
    body: ScheduleSandboxJobRequest,
    request: Request,
) -> dict[str, Any]:
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    correlation_id = uuid4()
    command = ScheduleSandboxJob(
        thread_ref=thread_ref,
        agent_role=body.agent_role,
        repo_url=body.repo_url,
        base_sha=body.base_sha,
        commands=body.commands,
        correlation_id=correlation_id,
    )
    sandbox_id = str(correlation_id)
    registry = get_sandbox_registry(request)
    registry[sandbox_id] = {
        "sandbox_id": sandbox_id,
        "status": SandboxStatus.PENDING.value,
        "repo_url": body.repo_url,
        "base_sha": body.base_sha,
        "commands": body.commands,
        "agent_role": body.agent_role.value,
        "thread_ref": asdict(thread_ref),
        "created_at": datetime.now(UTC).isoformat(),
    }
    return asdict(command)


@router.get("/sandboxes")
async def list_sandboxes(request: Request) -> list[dict[str, Any]]:
    """List all tracked sandbox jobs."""
    registry = get_sandbox_registry(request)
    return list(registry.values())


@router.get("/sandboxes/{sandbox_id}")
async def get_sandbox(sandbox_id: str, request: Request) -> dict[str, Any]:
    """Get details of a specific sandbox job."""
    registry = get_sandbox_registry(request)
    if sandbox_id not in registry:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    return registry[sandbox_id]


@router.delete("/sandboxes/{sandbox_id}", status_code=204)
async def destroy_sandbox(sandbox_id: str, request: Request) -> None:
    """Mark a sandbox as destroyed."""
    registry = get_sandbox_registry(request)
    if sandbox_id not in registry:
        raise HTTPException(status_code=404, detail="Sandbox not found")
    registry[sandbox_id]["status"] = SandboxStatus.DESTROYED.value
