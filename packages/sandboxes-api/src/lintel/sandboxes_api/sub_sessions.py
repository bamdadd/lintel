"""Agent sub-session endpoints: spawn, list, get, get result, update status."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import SubSessionCompleted, SubSessionFailed, SubSessionSpawned
from lintel.domain.types import SubSession, SubSessionStatus

if TYPE_CHECKING:
    from .sub_session_store import InMemorySubSessionStore

router = APIRouter()

sub_session_store_provider: StoreProvider[InMemorySubSessionStore] = StoreProvider()

MAX_SUB_SESSIONS_PER_PIPELINE = 10


class SpawnSubSessionRequest(BaseModel):
    parent_pipeline_run_id: str
    repo_url: str = ""
    prompt: str = ""


class UpdateSubSessionRequest(BaseModel):
    status: str
    result: str = ""
    error: str = ""


@router.post("/sandboxes/sub-sessions", status_code=201)
async def spawn_sub_session(
    body: SpawnSubSessionRequest,
    request: Request,
) -> dict[str, Any]:
    """Spawn a new agent sub-session for parallel research."""
    store = sub_session_store_provider.get()

    existing = await store.list_by_pipeline(body.parent_pipeline_run_id)
    if len(existing) >= MAX_SUB_SESSIONS_PER_PIPELINE:
        raise HTTPException(
            status_code=409,
            detail=f"Maximum {MAX_SUB_SESSIONS_PER_PIPELINE} sub-sessions per pipeline",
        )

    session_id = str(uuid.uuid4())
    sub_session = SubSession(
        session_id=session_id,
        parent_pipeline_run_id=body.parent_pipeline_run_id,
        repo_url=body.repo_url,
        prompt=body.prompt,
        status=SubSessionStatus.PENDING,
    )
    result: dict[str, Any] = await store.add(sub_session)
    await dispatch_event(
        request,
        SubSessionSpawned(
            payload={
                "resource_id": session_id,
                "parent_pipeline_run_id": body.parent_pipeline_run_id,
            },
        ),
        stream_id=f"sub-session:{session_id}",
    )
    return result


@router.get("/sandboxes/sub-sessions")
async def list_sub_sessions(
    parent_pipeline_run_id: str,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List sub-sessions for a pipeline run."""
    store = sub_session_store_provider.get()
    parsed_status: SubSessionStatus | None = None
    if status is not None:
        try:
            parsed_status = SubSessionStatus(status)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status!r}",
            ) from None
    return await store.list_by_pipeline(
        parent_pipeline_run_id,
        status=parsed_status,
    )


@router.get("/sandboxes/sub-sessions/{session_id}")
async def get_sub_session(session_id: str) -> dict[str, Any]:
    """Get a specific sub-session by ID."""
    store = sub_session_store_provider.get()
    result = await store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sub-session not found")
    return result


@router.get("/sandboxes/sub-sessions/{session_id}/result")
async def get_sub_session_result(session_id: str) -> dict[str, Any]:
    """Get the result of a completed sub-session."""
    store = sub_session_store_provider.get()
    result = await store.get(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sub-session not found")
    return {
        "session_id": session_id,
        "status": result["status"],
        "result": result["result"],
        "error": result["error"],
    }


@router.patch("/sandboxes/sub-sessions/{session_id}", status_code=200)
async def update_sub_session(
    session_id: str,
    body: UpdateSubSessionRequest,
    request: Request,
) -> dict[str, Any]:
    """Update sub-session status (e.g. mark running, completed, failed)."""
    store = sub_session_store_provider.get()
    try:
        new_status = SubSessionStatus(body.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status: {body.status!r}",
        ) from None

    updates: dict[str, Any] = {"status": new_status}
    if body.result:
        updates["result"] = body.result
    if body.error:
        updates["error"] = body.error
    if new_status in (SubSessionStatus.COMPLETED, SubSessionStatus.FAILED):
        from datetime import UTC, datetime

        updates["completed_at"] = datetime.now(UTC)

    updated = await store.update(session_id, updates)
    if updated is None:
        raise HTTPException(status_code=404, detail="Sub-session not found")

    if new_status == SubSessionStatus.COMPLETED:
        await dispatch_event(
            request,
            SubSessionCompleted(payload={"resource_id": session_id}),
            stream_id=f"sub-session:{session_id}",
        )
    elif new_status == SubSessionStatus.FAILED:
        await dispatch_event(
            request,
            SubSessionFailed(payload={"resource_id": session_id, "error": body.error}),
            stream_id=f"sub-session:{session_id}",
        )
    return updated
