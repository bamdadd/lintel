"""Audit entry endpoints (append-only)."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import AuditEntry

router = APIRouter()


class AuditEntryStore:
    """In-memory append-only store for audit entries."""

    def __init__(self) -> None:
        self._entries: dict[str, AuditEntry] = {}

    async def add(self, entry: AuditEntry) -> None:
        self._entries[entry.entry_id] = entry

    async def get(self, entry_id: str) -> AuditEntry | None:
        return self._entries.get(entry_id)

    async def list_all(
        self,
        *,
        actor_id: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
    ) -> list[AuditEntry]:
        entries = list(self._entries.values())
        if actor_id is not None:
            entries = [e for e in entries if e.actor_id == actor_id]
        if resource_type is not None:
            entries = [e for e in entries if e.resource_type == resource_type]
        if resource_id is not None:
            entries = [e for e in entries if e.resource_id == resource_id]
        return entries


def get_audit_entry_store(request: Request) -> AuditEntryStore:
    """Get audit entry store from app state."""
    return request.app.state.audit_entry_store  # type: ignore[no-any-return]


class CreateAuditEntryRequest(BaseModel):
    entry_id: str
    actor_id: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, object] | None = None
    timestamp: str = ""


@router.post("/audit", status_code=201)
async def record_audit_entry(
    body: CreateAuditEntryRequest,
    store: Annotated[AuditEntryStore, Depends(get_audit_entry_store)],
) -> dict[str, Any]:
    existing = await store.get(body.entry_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Audit entry already exists")
    timestamp = body.timestamp if body.timestamp else datetime.now(UTC).isoformat()
    entry = AuditEntry(
        entry_id=body.entry_id,
        actor_id=body.actor_id,
        actor_type=body.actor_type,
        action=body.action,
        resource_type=body.resource_type,
        resource_id=body.resource_id,
        details=body.details,
        timestamp=timestamp,
    )
    await store.add(entry)
    return asdict(entry)


@router.get("/audit")
async def list_audit_entries(
    store: Annotated[AuditEntryStore, Depends(get_audit_entry_store)],
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
) -> list[dict[str, Any]]:
    entries = await store.list_all(
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return [asdict(e) for e in entries]


@router.get("/audit/{entry_id}")
async def get_audit_entry(
    entry_id: str,
    store: Annotated[AuditEntryStore, Depends(get_audit_entry_store)],
) -> dict[str, Any]:
    entry = await store.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return asdict(entry)
