"""Sandbox management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.errors import SandboxNotFoundError
from lintel.contracts.types import SandboxConfig, SandboxJob, ThreadRef

router = APIRouter()


class SandboxStore:
    """In-memory sandbox metadata store."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, Any]] = {}

    async def add(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        self._sandboxes[sandbox_id] = metadata

    async def get(self, sandbox_id: str) -> dict[str, Any] | None:
        return self._sandboxes.get(sandbox_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._sandboxes.values())

    async def update(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        self._sandboxes[sandbox_id] = metadata

    async def remove(self, sandbox_id: str) -> None:
        self._sandboxes.pop(sandbox_id, None)


# ---------------------------------------------------------------------------
# Built-in sandbox presets
# ---------------------------------------------------------------------------

SANDBOX_PRESETS: dict[str, dict[str, Any]] = {
    "python": {
        "label": "Python 3.12",
        "description": "Minimal Python environment",
        "devcontainer": {
            "name": "python",
            "image": "mcr.microsoft.com/devcontainers/python:3.12",
            "features": [],
            "forwardPorts": [],
            "postCreateCommand": "",
            "postStartCommand": "",
            "remoteEnv": {},
            "customizations": {},
        },
    },
    "node": {
        "label": "Node.js 22",
        "description": "Node.js development environment",
        "devcontainer": {
            "name": "node",
            "image": "mcr.microsoft.com/devcontainers/javascript-node:22",
            "features": [],
            "forwardPorts": [],
            "postCreateCommand": "",
            "postStartCommand": "",
            "remoteEnv": {},
            "customizations": {},
        },
    },
    "claude-code": {
        "label": "Claude Code",
        "description": "Sandbox with Claude Code CLI for agentic coding tasks",
        "devcontainer": {
            "name": "claude-code",
            "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
            "features": [
                {
                    "id": "ghcr.io/devcontainers/features/node:1",
                    "options": {"version": "22"},
                },
                {
                    "id": "ghcr.io/devcontainers/features/python:1",
                    "options": {"version": "3.12"},
                },
                {
                    "id": "ghcr.io/devcontainers/features/git:1",
                    "options": {},
                },
            ],
            "forwardPorts": [],
            "postCreateCommand": "npm install -g @anthropic-ai/claude-code",
            "postStartCommand": "",
            "remoteEnv": {},
            "customizations": {},
        },
        "mounts": [
            {
                "source": "${localEnv:HOME}/.claude",
                "target": "/home/vscode/.claude",
                "type": "bind",
            },
        ],
    },
    "claude-code-full": {
        "label": "Claude Code (Full Stack)",
        "description": "Claude Code with Python, Node, Go, and common dev tools",
        "devcontainer": {
            "name": "claude-code-full",
            "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
            "features": [
                {
                    "id": "ghcr.io/devcontainers/features/node:1",
                    "options": {"version": "22"},
                },
                {
                    "id": "ghcr.io/devcontainers/features/python:1",
                    "options": {"version": "3.12"},
                },
                {
                    "id": "ghcr.io/devcontainers/features/go:1",
                    "options": {"version": "latest"},
                },
                {
                    "id": "ghcr.io/devcontainers/features/git:1",
                    "options": {},
                },
                {
                    "id": "ghcr.io/devcontainers/features/docker-in-docker:2",
                    "options": {},
                },
            ],
            "forwardPorts": [],
            "postCreateCommand": "npm install -g @anthropic-ai/claude-code",
            "postStartCommand": "",
            "remoteEnv": {},
            "customizations": {},
        },
        "mounts": [
            {
                "source": "${localEnv:HOME}/.claude",
                "target": "/home/vscode/.claude",
                "type": "bind",
            },
        ],
    },
    "base": {
        "label": "Base (Ubuntu)",
        "description": "Minimal Ubuntu devcontainer",
        "devcontainer": {
            "name": "base",
            "image": "mcr.microsoft.com/devcontainers/base:ubuntu",
            "features": [],
            "forwardPorts": [],
            "postCreateCommand": "",
            "postStartCommand": "",
            "remoteEnv": {},
            "customizations": {},
        },
    },
}


class DevcontainerFeature(BaseModel):
    """A devcontainer feature reference."""

    id: str
    options: dict[str, Any] = {}


class DevcontainerConfig(BaseModel):
    """Devcontainer-compatible sandbox configuration."""

    name: str = "sandbox"
    image: str = "mcr.microsoft.com/devcontainers/base:ubuntu"
    features: list[DevcontainerFeature] = []
    forward_ports: list[int] = []
    post_create_command: str = ""
    post_start_command: str = ""
    remote_env: dict[str, str] = {}
    customizations: dict[str, Any] = {}


class CreateSandboxRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    image: str = "python:3.12-slim"
    network_enabled: bool = False
    devcontainer: DevcontainerConfig | None = None


class ExecuteRequest(BaseModel):
    command: str
    workdir: str | None = None
    timeout_seconds: int = 300


class WriteFileRequest(BaseModel):
    path: str
    content: str


@router.get("/sandboxes/presets")
async def list_sandbox_presets() -> dict[str, dict[str, Any]]:
    """List available sandbox presets."""
    return SANDBOX_PRESETS


@router.get("/sandboxes")
async def list_sandboxes(request: Request) -> list[dict[str, Any]]:
    """List all sandbox environments."""
    store = request.app.state.sandbox_store
    return await store.list_all()


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
    entry: dict[str, Any] = {
        "sandbox_id": sandbox_id,
        "image": body.image,
        "network_enabled": body.network_enabled,
        "workspace_id": body.workspace_id,
        "channel_id": body.channel_id,
    }
    if body.devcontainer:
        entry["devcontainer"] = body.devcontainer.model_dump()
    store = request.app.state.sandbox_store
    await store.add(sandbox_id, entry)
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
        store = request.app.state.sandbox_store
        await store.remove(sandbox_id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None
