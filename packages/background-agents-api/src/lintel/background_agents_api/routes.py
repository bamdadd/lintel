"""Background agent session endpoints."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import structlog

from lintel.api_support.provider import StoreProvider
from lintel.background_agents_api.store import (
    InMemoryBackgroundSessionStore,
    SessionStatus,
)

logger = structlog.get_logger()

router = APIRouter()

session_store_provider: StoreProvider[InMemoryBackgroundSessionStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartSessionRequest(BaseModel):
    agent_role: str = Field(..., description="Agent role to execute (e.g. 'coder', 'reviewer')")
    task: str = Field(..., description="Task description for the agent")
    config: dict[str, Any] = Field(default_factory=dict, description="Additional config")


class SessionResponse(BaseModel):
    session_id: str
    agent_role: str
    task: str
    status: str
    created_at: float
    started_at: float | None = None
    finished_at: float | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)


class SessionDetailResponse(SessionResponse):
    logs: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Background task runner
# ---------------------------------------------------------------------------


async def _run_session(
    store: InMemoryBackgroundSessionStore,
    session_id: str,
) -> None:
    """Execute a background agent session.

    This is a placeholder that simulates work. A real implementation would
    invoke the agent runtime here.
    """
    try:
        await store.mark_running(session_id)
        await store.append_log(session_id, "info", "Session started")

        session = await store.get(session_id)
        if session is None:
            return

        await store.append_log(session_id, "info", f"Executing agent_role={session.agent_role}")

        # Placeholder: real implementation would call the agent runtime.
        # For now we just mark completed immediately so the API is exercisable.
        await store.mark_completed(session_id, result={"status": "stub_completed"})
        await store.append_log(session_id, "info", "Session finished")
    except asyncio.CancelledError:
        await store.mark_cancelled(session_id)
        await store.append_log(session_id, "warning", "Session cancelled")
    except Exception as exc:
        await store.mark_failed(session_id, str(exc))
        await store.append_log(session_id, "error", f"Session failed: {exc}")
        logger.exception("background_session_failed", session_id=session_id)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/agents/sessions", status_code=201)
async def start_session(
    body: StartSessionRequest,
) -> SessionResponse:
    """Start a detached background agent session."""
    store = session_store_provider.get()
    session = await store.create(
        agent_role=body.agent_role,
        task_description=body.task,
        config=body.config,
    )
    task = asyncio.create_task(_run_session(store, session.session_id))
    store.set_task(session.session_id, task)
    return SessionResponse(**_session_dict(session))


@router.get("/agents/sessions")
async def list_sessions(
    status: str | None = None,
) -> list[SessionResponse]:
    """List all background agent sessions, optionally filtered by status."""
    store = session_store_provider.get()
    sessions = await store.list_all()
    if status is not None:
        sessions = [s for s in sessions if s.status.value == status]
    return [SessionResponse(**_session_dict(s)) for s in sessions]


@router.get("/agents/sessions/{session_id}")
async def get_session(session_id: str) -> SessionDetailResponse:
    """Get status and logs for a background agent session."""
    store = session_store_provider.get()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    d = _session_dict(session)
    d["logs"] = [asdict(entry) for entry in session.logs]
    return SessionDetailResponse(**d)


@router.delete("/agents/sessions/{session_id}", status_code=204)
async def stop_session(session_id: str) -> None:
    """Stop and remove a background agent session."""
    store = session_store_provider.get()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    await store.delete(session_id)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _session_dict(session: Any) -> dict[str, Any]:  # noqa: ANN401
    """Convert a BackgroundSession to a plain dict for response models."""
    return {
        "session_id": session.session_id,
        "agent_role": session.agent_role,
        "task": session.task,
        "status": session.status.value
        if isinstance(session.status, SessionStatus)
        else session.status,
        "created_at": session.created_at,
        "started_at": session.started_at,
        "finished_at": session.finished_at,
        "result": session.result,
        "error": session.error,
        "config": session.config,
    }
