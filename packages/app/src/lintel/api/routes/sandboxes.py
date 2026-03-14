"""Sandbox management endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.data_models import SandboxMetadata
from lintel.contracts.errors import SandboxNotFoundError
from lintel.contracts.events import (
    SandboxCommandExecuted,
    SandboxCreated,
    SandboxDestroyed,
    SandboxFileWritten,
)
from lintel.contracts.types import SandboxConfig, SandboxJob, ThreadRef

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
        from lintel.api.routes.settings import get_general_settings

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
        await dispatch_event(
            request,
            SandboxFileWritten(payload={"resource_id": sandbox_id, "path": body.path}),
            stream_id=f"sandbox:{sandbox_id}",
        )
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
        # Use cat via execute — more reliable than get_archive with cap_drop
        result = await manager.execute(
            sandbox_id,
            SandboxJob(command=f"cat {path}", timeout_seconds=10),
        )
        if result.exit_code != 0:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot read file: {result.stderr.strip()}",
            )
        return {"path": path, "content": result.stdout}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.get("/sandboxes/{sandbox_id}/tree")
async def get_file_tree(
    sandbox_id: str,
    request: Request,
    path: str = "/workspace",
    depth: int = 3,
) -> dict[str, Any]:
    """Get a file tree from the sandbox, similar to Docker Desktop's file browser."""
    manager = request.app.state.sandbox_manager
    try:
        # Use find to build a structured tree — fast and reliable
        result = await manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"find {path} -maxdepth {depth}"
                    f" -not -path '*/.git/*' -not -path '*/.git'"
                    f" -not -path '*/node_modules/*'"
                    f" -not -path '*/__pycache__/*'"
                    f" -not -path '*/.venv/*'"
                    " | head -2000"
                ),
                timeout_seconds=15,
            ),
        )
        if result.exit_code != 0:
            return {"path": path, "children": [], "error": result.stderr}

        lines = [ln for ln in result.stdout.strip().split("\n") if ln and ln != path]

        # Get file/dir info with stat
        stat_result = await manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    f"find {path} -maxdepth {depth}"
                    f" -not -path '*/.git/*' -not -path '*/.git'"
                    f" -not -path '*/node_modules/*'"
                    f" -not -path '*/__pycache__/*'"
                    f" -not -path '*/.venv/*'"
                    " -printf '%y %s %p\\n'"
                    " | head -2000"
                ),
                timeout_seconds=15,
            ),
        )

        # Build lookup: path -> {type, size}
        info: dict[str, dict[str, Any]] = {}
        if stat_result.exit_code == 0:
            for ln in stat_result.stdout.strip().split("\n"):
                parts = ln.split(" ", 2)
                if len(parts) == 3:
                    info[parts[2]] = {
                        "type": "directory" if parts[0] == "d" else "file",
                        "size": int(parts[1]) if parts[0] != "d" else 0,
                    }

        # Build tree structure
        def build_tree(
            root: str,
            paths: list[str],
        ) -> list[dict[str, Any]]:
            children_map: dict[str, list[str]] = {}
            direct: list[str] = []
            root_depth = root.rstrip("/").count("/")

            for p in paths:
                p_depth = p.rstrip("/").count("/")
                if p_depth == root_depth + 1:
                    direct.append(p)
                elif p_depth > root_depth + 1:
                    # Find the direct parent at root_depth+1
                    parts = p.split("/")
                    parent = "/".join(parts[: root_depth + 2])
                    children_map.setdefault(parent, []).append(p)

            nodes: list[dict[str, Any]] = []
            for d in sorted(direct):
                meta = info.get(d, {"type": "file", "size": 0})
                name = d.rsplit("/", 1)[-1]
                node: dict[str, Any] = {
                    "name": name,
                    "path": d,
                    "type": meta["type"],
                }
                if meta["type"] == "file":
                    node["size"] = meta["size"]
                else:
                    sub_paths = children_map.get(d, [])
                    node["children"] = build_tree(d, sub_paths)
                nodes.append(node)

            # Sort: directories first, then files, alphabetical
            nodes.sort(key=lambda n: (0 if n["type"] == "directory" else 1, n["name"]))
            return nodes

        return {
            "path": path,
            "children": build_tree(path, lines),
        }
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.post("/sandboxes/{sandbox_id}/cleanup-workspace")
async def cleanup_workspace(
    sandbox_id: str,
    request: Request,
) -> dict[str, str]:
    """Remove all files from /workspace in the sandbox."""
    manager = request.app.state.sandbox_manager
    try:
        result = await manager.execute(
            sandbox_id,
            SandboxJob(
                command=(
                    "rm -rf /workspace/* /workspace/.[!.]* /workspace/..?* 2>/dev/null; echo ok"
                ),
                timeout_seconds=30,
            ),
        )
        if result.exit_code != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Cleanup failed: {result.stderr.strip()}",
            )
        return {"status": "cleaned", "sandbox_id": sandbox_id}
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
