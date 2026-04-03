"""Sandbox lifecycle endpoints: presets, create, list, get status, destroy, cleanup."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
from lintel.sandbox.types import (
    DatabaseReplica,
    NetworkEndpoint,
    NetworkPolicy,
    SandboxBackend,
    SandboxConfig,
)

if TYPE_CHECKING:
    from lintel.sandbox.protocols import SandboxManager

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


class NetworkEndpointConfig(BaseModel):
    """An authorized network endpoint for egress whitelisting."""

    host: str
    port: int | None = None
    protocol: str = "tcp"


class NetworkPolicyConfig(BaseModel):
    """Network isolation policy for a sandbox."""

    allowed_endpoints: list[NetworkEndpointConfig] = []
    isolate: bool = True


class ReplicaConnectionConfig(BaseModel):
    """Inline database replica connection for a sandbox."""

    name: str
    host: str
    port: int = 5432
    database: str = "postgres"
    read_only: bool = True
    credential_ref: str = ""


class CreateSandboxRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    preset: str | None = None
    image: str = "lintel-sandbox:latest"
    network_enabled: bool = False
    network_policy: NetworkPolicyConfig | None = None
    devcontainer: DevcontainerConfig | None = None
    mounts: list[MountConfig] = []
    backend: str = "docker"  # "docker" or "openshell"
    project_id: str | None = None
    replica_connections: list[ReplicaConnectionConfig] = []


def _replicas_to_env(
    replicas: list[ReplicaConnectionConfig],
) -> list[tuple[str, str]]:
    """Convert replica configs to environment variable pairs for sandbox injection.

    For each replica named ``foo``, injects:
      DB_REPLICA_FOO_HOST, DB_REPLICA_FOO_PORT, DB_REPLICA_FOO_DATABASE,
      DB_REPLICA_FOO_READ_ONLY, DB_REPLICA_FOO_CREDENTIAL_REF
    Plus DB_REPLICA_NAMES as a comma-separated list of all replica names.
    """
    env: list[tuple[str, str]] = []
    names: list[str] = []
    for r in replicas:
        key = r.name.upper().replace("-", "_")
        names.append(r.name)
        env.append((f"DB_REPLICA_{key}_HOST", r.host))
        env.append((f"DB_REPLICA_{key}_PORT", str(r.port)))
        env.append((f"DB_REPLICA_{key}_DATABASE", r.database))
        env.append((f"DB_REPLICA_{key}_READ_ONLY", str(r.read_only).lower()))
        if r.credential_ref:
            env.append((f"DB_REPLICA_{key}_CREDENTIAL_REF", r.credential_ref))
    if names:
        env.append(("DB_REPLICA_NAMES", ",".join(names)))
    return env


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

    # Resolve backend and pick the appropriate manager
    try:
        backend = SandboxBackend(body.backend)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown backend: {body.backend!r}. Use 'docker' or 'openshell'.",
        ) from None

    if backend == SandboxBackend.OPENSHELL:
        manager = _get_or_create_openshell_manager(request)
    else:
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

    # Build network policy from request
    net_policy: NetworkPolicy | None = None
    if body.network_policy is not None:
        net_policy = NetworkPolicy(
            allowed_endpoints=tuple(
                NetworkEndpoint(host=ep.host, port=ep.port, protocol=ep.protocol)
                for ep in body.network_policy.allowed_endpoints
            ),
            isolate=body.network_policy.isolate,
        )

    # Collect replica connections: inline from request + project-level from store
    all_replicas: list[ReplicaConnectionConfig] = list(body.replica_connections)
    if body.project_id:
        replica_store = getattr(request.app.state, "replica_config_store", None)
        if replica_store is not None:
            project_replicas = await replica_store.list_for_project(body.project_id)
            for pr in project_replicas:
                all_replicas.append(
                    ReplicaConnectionConfig(
                        name=pr.name,
                        host=pr.host,
                        port=pr.port,
                        database=pr.database,
                        read_only=pr.read_only,
                        credential_ref=pr.credential_ref,
                    )
                )

    # Build replica domain objects and inject env vars
    replica_domain = tuple(
        DatabaseReplica(
            name=r.name,
            host=r.host,
            port=r.port,
            database=r.database,
            read_only=r.read_only,
            credential_ref=r.credential_ref,
        )
        for r in all_replicas
    )
    replica_env = frozenset(_replicas_to_env(all_replicas))

    config = SandboxConfig(
        image=image,
        network_enabled=body.network_enabled,
        mounts=resolved_mounts,
        backend=backend,
        network_policy=net_policy,
        replica_connections=replica_domain,
        environment=replica_env,
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
        "backend": backend.value,
    }
    if body.network_policy is not None:
        entry["network_policy"] = body.network_policy.model_dump()
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


def _get_or_create_openshell_manager(request: Request) -> SandboxManager:
    """Return the OpenShell manager, lazily creating it on first use."""
    mgr: SandboxManager | None = getattr(request.app.state, "openshell_manager", None)
    if mgr is None:
        from lintel.sandbox.openshell_backend import OpenShellSandboxManager

        mgr = OpenShellSandboxManager()
        request.app.state.openshell_manager = mgr
    return mgr


async def _resolve_manager(request: Request, sandbox_id: str) -> SandboxManager:
    """Pick the correct sandbox manager based on stored metadata backend."""
    store = request.app.state.sandbox_store
    meta = await store.get(sandbox_id)
    if meta and meta.get("backend") == SandboxBackend.OPENSHELL.value:
        return _get_or_create_openshell_manager(request)
    return request.app.state.sandbox_manager  # type: ignore[no-any-return]


@router.get("/sandboxes/{sandbox_id}")
async def get_sandbox_status(
    sandbox_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get sandbox status."""
    manager = await _resolve_manager(request, sandbox_id)
    try:
        status = await manager.get_status(sandbox_id)
        return {"sandbox_id": sandbox_id, "status": status.value}
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None


@router.delete("/sandboxes/{sandbox_id}", status_code=204)
async def destroy_sandbox(sandbox_id: str, request: Request) -> None:
    """Destroy a sandbox."""
    manager = await _resolve_manager(request, sandbox_id)
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
    all_sandboxes = await store.list_all()
    unassigned = [s for s in all_sandboxes if not s.get("pipeline_id")]
    destroyed: list[str] = []
    failed: list[str] = []
    for s in unassigned:
        sid = s.get("sandbox_id", "")
        if not sid:
            continue
        try:
            manager = await _resolve_manager(request, sid)
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
