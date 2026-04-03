"""Session hibernation and lifecycle endpoints: hibernate, resume, timeout config, cost."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.sandbox.errors import (
    SandboxNotFoundError,
    SessionAlreadyInStateError,
)
from lintel.sandbox.events import (
    SandboxSessionHibernated,
    SandboxSessionResumed,
    SandboxSessionTerminated,
)
from lintel.sandbox.types import TimeoutConfig

if TYPE_CHECKING:
    from lintel.sandbox.session_lifecycle import SessionLifecycleManager
    from lintel.sandbox.types import SessionLifecycle

router = APIRouter()

lifecycle_manager_provider: StoreProvider[SessionLifecycleManager] = StoreProvider()


def _lifecycle_to_dict(lifecycle: SessionLifecycle) -> dict[str, Any]:
    """Convert a SessionLifecycle dataclass to a JSON-friendly dict."""
    d = asdict(lifecycle)
    for key in ("created_at", "last_activity_at", "hibernated_at", "resumed_at", "terminated_at"):
        val = d.get(key)
        if val is not None:
            d[key] = val.isoformat()
    d["state"] = lifecycle.state.value
    return d


class HibernateRequest(BaseModel):
    snapshot_id: str = ""


class TimeoutConfigRequest(BaseModel):
    idle_timeout_seconds: int = 1800
    max_lifetime_seconds: int = 14400


@router.post("/sandboxes/{sandbox_id}/hibernate")
async def hibernate_session(
    sandbox_id: str,
    body: HibernateRequest,
    request: Request,
) -> dict[str, Any]:
    """Hibernate a sandbox session: snapshot state and stop the container."""
    mgr = lifecycle_manager_provider.get()

    # Auto-register if not tracked yet
    if mgr.get_or_none(sandbox_id) is None:
        mgr.register(sandbox_id)

    # If no snapshot_id provided, create one via the snapshot endpoint
    snapshot_id = body.snapshot_id
    if not snapshot_id:
        import uuid

        snapshot_id = f"auto-{uuid.uuid4()!s:.8}"

    try:
        session = mgr.hibernate(sandbox_id, snapshot_id)
    except SessionAlreadyInStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None

    # Update sandbox store status
    sandbox_store = request.app.state.sandbox_store
    meta = await sandbox_store.get(sandbox_id)
    if meta is not None:
        meta["status"] = "hibernated"
        meta["snapshot_id"] = snapshot_id
        await sandbox_store.update(sandbox_id, meta)

    await dispatch_event(
        request,
        SandboxSessionHibernated(
            payload={
                "resource_id": sandbox_id,
                "snapshot_id": snapshot_id,
                "cost": asdict(session.cost),
            },
        ),
        stream_id=f"sandbox:{sandbox_id}",
    )
    return _lifecycle_to_dict(session)


@router.post("/sandboxes/{sandbox_id}/resume")
async def resume_session(
    sandbox_id: str,
    request: Request,
) -> dict[str, Any]:
    """Resume a hibernated sandbox session from its snapshot."""
    mgr = lifecycle_manager_provider.get()
    try:
        session = mgr.resume(sandbox_id)
    except SessionAlreadyInStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None

    # Update sandbox store status
    sandbox_store = request.app.state.sandbox_store
    meta = await sandbox_store.get(sandbox_id)
    if meta is not None:
        meta["status"] = "running"
        await sandbox_store.update(sandbox_id, meta)

    await dispatch_event(
        request,
        SandboxSessionResumed(
            payload={
                "resource_id": sandbox_id,
                "snapshot_id": session.snapshot_id,
            },
        ),
        stream_id=f"sandbox:{sandbox_id}",
    )
    return _lifecycle_to_dict(session)


@router.post("/sandboxes/{sandbox_id}/terminate")
async def terminate_session(
    sandbox_id: str,
    request: Request,
) -> dict[str, Any]:
    """Terminate a sandbox session and record final cost."""
    mgr = lifecycle_manager_provider.get()

    if mgr.get_or_none(sandbox_id) is None:
        mgr.register(sandbox_id)

    try:
        session = mgr.terminate(sandbox_id)
    except SessionAlreadyInStateError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Sandbox not found") from None

    await dispatch_event(
        request,
        SandboxSessionTerminated(
            payload={
                "resource_id": sandbox_id,
                "cost": asdict(session.cost),
            },
        ),
        stream_id=f"sandbox:{sandbox_id}",
    )
    return _lifecycle_to_dict(session)


@router.get("/sandboxes/{sandbox_id}/session")
async def get_session_lifecycle(
    sandbox_id: str,
) -> dict[str, Any]:
    """Get session lifecycle state and cost for a sandbox."""
    mgr = lifecycle_manager_provider.get()
    try:
        session = mgr.get(sandbox_id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return _lifecycle_to_dict(session)


@router.put("/sandboxes/{sandbox_id}/timeout-config")
async def update_timeout_config(
    sandbox_id: str,
    body: TimeoutConfigRequest,
) -> dict[str, Any]:
    """Update idle timeout and max lifetime configuration for a session."""
    mgr = lifecycle_manager_provider.get()

    if mgr.get_or_none(sandbox_id) is None:
        mgr.register(sandbox_id)

    try:
        session = mgr.update_timeout_config(
            sandbox_id,
            TimeoutConfig(
                idle_timeout_seconds=body.idle_timeout_seconds,
                max_lifetime_seconds=body.max_lifetime_seconds,
            ),
        )
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return _lifecycle_to_dict(session)


@router.get("/sandboxes/{sandbox_id}/cost")
async def get_session_cost(
    sandbox_id: str,
) -> dict[str, Any]:
    """Get accumulated cost for a sandbox session."""
    mgr = lifecycle_manager_provider.get()
    try:
        session = mgr.get(sandbox_id)
    except SandboxNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None
    return {
        "sandbox_id": sandbox_id,
        "state": session.state.value,
        "cost": asdict(session.cost),
        "total_cost_units": session.cost.total_cost_units,
    }


@router.get("/sandboxes/sessions/idle")
async def list_idle_sessions() -> dict[str, Any]:
    """List sessions that have exceeded their idle timeout."""
    mgr = lifecycle_manager_provider.get()
    idle_ids = mgr.check_idle_sessions()
    return {"idle_sandbox_ids": idle_ids, "count": len(idle_ids)}


@router.get("/sandboxes/sessions/expired")
async def list_expired_sessions() -> dict[str, Any]:
    """List sessions that have exceeded their max lifetime."""
    mgr = lifecycle_manager_provider.get()
    expired_ids = mgr.check_expired_sessions()
    return {"expired_sandbox_ids": expired_ids, "count": len(expired_ids)}
