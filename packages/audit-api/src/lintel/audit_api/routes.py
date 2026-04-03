"""Audit entry endpoints (append-only with tamper-proof hash chain)."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from lintel.api_support.provider import StoreProvider
from lintel.audit_api.hash_chain import HashChainAuditStore
from lintel.audit_api.store import AuditEntryStore
from lintel.domain.types import AuditEntry

router = APIRouter()

audit_entry_store_provider: StoreProvider = StoreProvider()


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
    store: AuditEntryStore = Depends(audit_entry_store_provider),  # noqa: B008
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


class PaginatedAuditResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int
    limit: int
    offset: int


@router.get("/audit")
async def list_audit_entries(
    store: AuditEntryStore = Depends(audit_entry_store_provider),  # noqa: B008
    actor_id: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> PaginatedAuditResponse:
    entries = await store.list_all(
        actor_id=actor_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    # Sort by timestamp descending (most recent first)
    entries.sort(key=lambda e: e.timestamp, reverse=True)
    total = len(entries)
    page = entries[offset : offset + limit]
    return PaginatedAuditResponse(
        items=[asdict(e) for e in page],
        total=total,
        limit=limit,
        offset=offset,
    )


class VerifyResponse(BaseModel):
    valid: bool
    entries_checked: int
    broken_at: str | None = None


@router.get("/audit/verify")
async def verify_audit_chain(
    store: AuditEntryStore = Depends(audit_entry_store_provider),  # noqa: B008
) -> VerifyResponse:
    if not isinstance(store, HashChainAuditStore):
        raise HTTPException(
            status_code=501,
            detail="Hash chain verification requires HashChainAuditStore",
        )
    result = await store.verify_chain()
    return VerifyResponse(
        valid=result.valid,
        entries_checked=result.entries_checked,
        broken_at=result.broken_at,
    )


class ExportResponse(BaseModel):
    items: list[dict[str, Any]]
    total: int


@router.get("/audit/export")
async def export_audit_entries(
    store: AuditEntryStore = Depends(audit_entry_store_provider),  # noqa: B008
    from_ts: str | None = None,
    to_ts: str | None = None,
) -> ExportResponse:
    if not isinstance(store, HashChainAuditStore):
        raise HTTPException(
            status_code=501,
            detail="Export requires HashChainAuditStore",
        )
    entries = await store.export_entries(from_ts=from_ts, to_ts=to_ts)
    items = [asdict(e) for e in entries]
    return ExportResponse(items=items, total=len(items))


@router.get("/audit/{entry_id}")
async def get_audit_entry(
    entry_id: str,
    store: AuditEntryStore = Depends(audit_entry_store_provider),  # noqa: B008
) -> dict[str, Any]:
    entry = await store.get(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Audit entry not found")
    return asdict(entry)
