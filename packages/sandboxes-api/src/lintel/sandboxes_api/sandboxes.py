"""Sandbox lifecycle endpoints: presets, create, list, get status, destroy, cleanup."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.contracts.types import ThreadRef
from lintel.persistence.data_models import SandboxMetadata
from lintel.sandbox.errors import SandboxNotFoundError
from lintel.sandbox.events import (
    SandboxCreated,
    SandboxDestroyed,
)
from lintel.sandbox.types import SandboxConfig

router = APIRouter()


class SandboxStore:
    """In-memory sandbox metadata store."""

    def __init__(self) -> None:
        self._sandboxes: dict[str, dict[str, Any]] = {}

    async def add(self, sandbox_id: str, metadata: dict[str, Any]) -> None:
        validated = SandboxMetadata.model_validate({"sandbox_id": sandbox_id, **metadata})
        self._sandboxes[sandbox_id] = validated.model_dump()

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
            "image": "lintel-sandbox:latest",
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
            "postCreateCommand": "",
            "postStartCommand": "",
            "remoteEnv": {},
            "customizations": {},
        },
        "mounts": [],
    },
    "claude-code-full": {
        "label": "Claude Code (Full Stack)",
        "description": "Claude Code with Python, Node, Go, and common dev tools",
        "devcontainer": {
            "name": "claude-code-full",
            "image": "lintel-sandbox:latest",
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
            "postCreateCommand": "",
            "postStartCommand": "",
            "remoteEnv": {},
            "customizations": {},
        },
        "mounts": [],
    },
    "base": {
        "label": "Base (Ubuntu)",
        "description": "Minimal Ubuntu devcontainer",
        "devcontainer": {
            "name": "base",
            "image": "lintel-sandbox:latest",
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
    image: str = "lintel-sandbox:latest"
    features: list[DevcontainerFeature] = []
    forward_ports: list[int] = []
    post_create_command: str = ""
    post_start_command: str = ""
    remote_env: dict[str, str] = {}
    customizations: dict[str, Any] = {}


class MountConfig(BaseModel):
    """A bind mount for the sandbox container."""

    source: str
    target: str
    type: str = "bind"


class CreateSandboxRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    preset: str | None = None
    image: str = "lintel-sandbox:latest"
    network_enabled: bool = False
    devcontainer: DevcontainerConfig | None = None
    mounts: list[MountConfig] = []


@router.get("/sandboxes/presets")
async def list_sandbox_presets() -> dict[str, dict[str, Any]]:
    """List available sandbox presets."""
    return SANDBOX_PRESETS


@router.get("/sandboxes")
async def list_sandboxes(request: Request) -> list[dict[str, Any]]:
    """List all sandbox environments."""
    store = request.app.state.sandbox_store
    result: list[dict[str, Any]] = await store.list_all()
    return result


@router.post("/sandboxes", status_code=201)
async def create_sandbox(
    body: CreateSandboxRequest,
    request: Request,
) -> dict[str, str]:
    """Create a new sandbox environment."""
    import os

    # Enforce max_sandboxes limit from general settings
    sandbox_store = request.app.state.sandbox_store
    general_settings = getattr(request.app.state, "general_settings", None)
    if general_settings is not None:
        max_sandboxes = general_settings.get("max_sandboxes", 20)
    else:
        from lintel.settings_api.routes import get_general_settings

        general_settings = get_general_settings(request)
        max_sandboxes = general_settings.get("max_sandboxes", 20)
    current = await sandbox_store.list_all()
    if len(current) >= max_sandboxes:
        raise HTTPException(
            status_code=429,
            detail=f"Sandbox limit reached ({len(current)}/{max_sandboxes}). "
            "Destroy unused sandboxes or increase max_sandboxes in settings.",
        )

    manager = request.app.state.sandbox_manager
    # Resolve preset if specified
    mounts_raw: list[dict[str, str]] = []
    if body.preset:
        preset = SANDBOX_PRESETS.get(body.preset)
        if not preset:
            raise HTTPException(status_code=400, detail=f"Unknown preset: {body.preset}")
        image = preset["devcontainer"]["image"]
        mounts_raw = list(preset.get("mounts", []))
    else:
        image = body.image

    # Merge request-level mounts (override or append)
    for m in body.mounts:
        mounts_raw.append(m.model_dump())

    # Resolve ${localEnv:HOME} and other env vars in mount sources
    def _resolve_env(s: str) -> str:
        import re

        return re.sub(
            r"\$\{localEnv:(\w+)\}",
            lambda m: os.environ.get(m.group(1), ""),
            s,
        )

    resolved_mounts = tuple(
        (_resolve_env(m["source"]), m["target"], m.get("type", "bind"))
        for m in mounts_raw
        if _resolve_env(m["source"])  # skip mounts with unresolvable source
    )

    config = SandboxConfig(
        image=image,
        network_enabled=body.network_enabled,
        mounts=resolved_mounts,
    )
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    sandbox_id = await manager.create(config, thread_ref)
    entry: dict[str, Any] = {
        "sandbox_id": sandbox_id,
        "image": image,
        "network_enabled": body.network_enabled,
        "workspace_id": body.workspace_id,
        "channel_id": body.channel_id,
        "mounts": [{"source": s, "target": t, "type": tp} for s, t, tp in resolved_mounts],
    }
    if body.devcontainer:
        entry["devcontainer"] = body.devcontainer.model_dump()
    store = request.app.state.sandbox_store
    await store.add(sandbox_id, entry)
    await dispatch_event(
        request,
        SandboxCreated(payload={"resource_id": sandbox_id, "image": image}),
        stream_id=f"sandbox:{sandbox_id}",
    )
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


@router.delete("/sandboxes/{sandbox_id}", status_code=204)
async def destroy_sandbox(sandbox_id: str, request: Request) -> None:
    """Destroy a sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        await manager.destroy(sandbox_id)
        store = request.app.state.sandbox_store
        await store.remove(sandbox_id)
        await dispatch_event(
            request,
            SandboxDestroyed(payload={"resource_id": sandbox_id}),
            stream_id=f"sandbox:{sandbox_id}",
        )
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.post("/sandboxes/cleanup-unassigned")
async def cleanup_unassigned_sandboxes(request: Request) -> dict[str, Any]:
    """Destroy all sandboxes that are not assigned to a pipeline."""
    store = request.app.state.sandbox_store
    manager = request.app.state.sandbox_manager
    all_sandboxes = await store.list_all()
    unassigned = [s for s in all_sandboxes if not s.get("pipeline_id")]
    destroyed: list[str] = []
    failed: list[str] = []
    for s in unassigned:
        sid = s.get("sandbox_id", "")
        if not sid:
            continue
        try:
            await manager.destroy(sid)
            await store.remove(sid)
            await dispatch_event(
                request,
                SandboxDestroyed(payload={"resource_id": sid}),
                stream_id=f"sandbox:{sid}",
            )
            destroyed.append(sid)
        except Exception:
            failed.append(sid)
    return {"destroyed": len(destroyed), "failed": len(failed), "ids": destroyed}
