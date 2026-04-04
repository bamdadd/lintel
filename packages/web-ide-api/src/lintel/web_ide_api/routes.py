"""Web IDE session CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.web_ide_api.store import IDESession, IDESessionStatus, InMemoryIDESessionStore

router = APIRouter()

ide_session_store_provider: StoreProvider[InMemoryIDESessionStore] = StoreProvider()


class CreateIDESessionRequest(BaseModel):
    """Request to create a new IDE session."""

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    sandbox_id: str
    project_id: str
    workspace_path: str = "/workspace"
    port: int = 8080


class UpdateIDESessionRequest(BaseModel):
    """Request to update an IDE session."""

    status: IDESessionStatus | None = None
    proxy_url: str | None = None


def _session_to_dict(session: IDESession) -> dict[str, Any]:
    return asdict(session)


@router.post("/ide/sessions", status_code=201)
async def create_ide_session(
    body: CreateIDESessionRequest,
    store: InMemoryIDESessionStore = Depends(ide_session_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Create a new Web IDE session tied to a sandbox."""
    existing = await store.get(body.session_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="IDE session already exists")
    session = IDESession(
        session_id=body.session_id,
        sandbox_id=body.sandbox_id,
        project_id=body.project_id,
        workspace_path=body.workspace_path,
        port=body.port,
        proxy_url=f"/ide/sessions/{body.session_id}/proxy",
    )
    await store.add(session)
    return _session_to_dict(session)


@router.get("/ide/sessions")
async def list_ide_sessions(
    project_id: str | None = None,
    store: InMemoryIDESessionStore = Depends(ide_session_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all IDE sessions, optionally filtered by project."""
    sessions = await store.list_all(project_id=project_id)
    return [_session_to_dict(s) for s in sessions]


@router.get("/ide/sessions/{session_id}")
async def get_ide_session(
    session_id: str,
    store: InMemoryIDESessionStore = Depends(ide_session_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific IDE session by ID."""
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="IDE session not found")
    return _session_to_dict(session)


@router.patch("/ide/sessions/{session_id}")
async def update_ide_session(
    session_id: str,
    body: UpdateIDESessionRequest,
    store: InMemoryIDESessionStore = Depends(ide_session_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Update an IDE session (e.g. change status or proxy URL)."""
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="IDE session not found")
    updates = body.model_dump(exclude_none=True)
    updated = IDESession(**{**asdict(session), **updates})
    await store.update(updated)
    return _session_to_dict(updated)


@router.delete("/ide/sessions/{session_id}", status_code=204)
async def delete_ide_session(
    session_id: str,
    store: InMemoryIDESessionStore = Depends(ide_session_store_provider),  # noqa: B008
) -> None:
    """Stop and remove an IDE session."""
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="IDE session not found")
    await store.remove(session_id)
