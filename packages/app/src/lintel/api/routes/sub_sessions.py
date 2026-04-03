"""Sub-session API routes — list and inspect agent sub-sessions."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.agents.sub_sessions import SubSessionManager

router = APIRouter()

_sub_session_manager_provider: StoreProvider[SubSessionManager] = StoreProvider()


@router.get("/sub-sessions")
async def list_sub_sessions(parent_session_id: str | None = None) -> list[dict[str, Any]]:
    mgr = _sub_session_manager_provider.get()
    sessions = mgr.list_for_parent(parent_session_id) if parent_session_id else mgr.list_all()
    return [asdict(s) for s in sessions]


@router.get("/sub-sessions/{session_id}")
async def get_sub_session(session_id: str) -> dict[str, Any]:
    mgr = _sub_session_manager_provider.get()
    session = mgr.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Sub-session not found")
    return asdict(session)
