"""Multiplayer session CRUD and join/leave endpoints."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.domain.types import Participant, Session
from lintel.multiplayer_sessions_api.store import InMemorySessionStore  # noqa: TC001

router = APIRouter()

session_store_provider: StoreProvider[InMemorySessionStore] = StoreProvider()


# --- Request / Response models ---


class CreateSessionRequest(BaseModel):
    """Request body for creating a session."""

    name: str
    created_by: str


class JoinSessionRequest(BaseModel):
    """Request body for joining a session."""

    user_id: str
    role: str = Field(default="member")


class LeaveSessionRequest(BaseModel):
    """Request body for leaving a session."""

    user_id: str


# --- Endpoints ---


@router.post("/sessions", status_code=201)
async def create_session(body: CreateSessionRequest) -> dict[str, Any]:
    """Create a new multiplayer session."""
    store = session_store_provider.get()
    session = Session(
        session_id=str(uuid4()),
        name=body.name,
        created_by=body.created_by,
        participants=(
            Participant(
                user_id=body.created_by,
                role="owner",
                joined_at=datetime.now(tz=UTC).isoformat(),
            ),
        ),
        status="active",
    )
    return await store.add(session)


@router.get("/sessions")
async def list_sessions() -> list[dict[str, Any]]:
    """List all multiplayer sessions."""
    store = session_store_provider.get()
    return await store.list_all()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> dict[str, Any]:
    """Get a specific session by ID."""
    store = session_store_provider.get()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/join")
async def join_session(session_id: str, body: JoinSessionRequest) -> dict[str, Any]:
    """Join an existing session."""
    store = session_store_provider.get()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if session["status"] != "active":
        raise HTTPException(status_code=400, detail="Session is not active")

    participants: list[dict[str, Any]] = list(session.get("participants", []))
    for p in participants:
        if p["user_id"] == body.user_id:
            raise HTTPException(status_code=409, detail="Already a participant")

    participants.append(
        {
            "user_id": body.user_id,
            "role": body.role,
            "joined_at": datetime.now(tz=UTC).isoformat(),
        }
    )
    updated = await store.update(session_id, {"participants": participants})
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated


@router.post("/sessions/{session_id}/leave")
async def leave_session(session_id: str, body: LeaveSessionRequest) -> dict[str, Any]:
    """Leave an existing session."""
    store = session_store_provider.get()
    session = await store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    participants: list[dict[str, Any]] = list(session.get("participants", []))
    new_participants = [p for p in participants if p["user_id"] != body.user_id]
    if len(new_participants) == len(participants):
        raise HTTPException(status_code=404, detail="User not in session")

    updated = await store.update(session_id, {"participants": new_participants})
    if updated is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return updated
