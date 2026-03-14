"""PII operation endpoints."""

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.commands import RevealPII
from lintel.contracts.events import VaultRevealRequested
from lintel.contracts.types import ThreadRef

router = APIRouter()


class RevealPIIRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    placeholder: str
    requester_id: str
    reason: str


def get_vault_log(request: Request) -> list[dict[str, Any]]:
    """Get vault activity log from app state."""
    if not hasattr(request.app.state, "vault_log"):
        request.app.state.vault_log = []
    return request.app.state.vault_log  # type: ignore[no-any-return]


def get_pii_stats(request: Request) -> dict[str, int]:
    """Get PII stats counters from app state."""
    if not hasattr(request.app.state, "pii_stats"):
        request.app.state.pii_stats = {
            "total_scanned": 0,
            "total_detected": 0,
            "total_anonymised": 0,
            "total_blocked": 0,
            "total_reveals": 0,
        }
    return request.app.state.pii_stats  # type: ignore[no-any-return]


@router.post("/pii/reveal")
async def reveal_pii(body: RevealPIIRequest, request: Request) -> dict[str, Any]:
    """Reveal a PII placeholder for a given thread."""
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    command = RevealPII(
        thread_ref=thread_ref,
        placeholder=body.placeholder,
        requester_id=body.requester_id,
        reason=body.reason,
    )
    log = get_vault_log(request)
    log.append(
        {
            "action": "reveal_requested",
            "placeholder": body.placeholder,
            "requester_id": body.requester_id,
            "reason": body.reason,
            "thread_ref": asdict(thread_ref),
            "timestamp": datetime.now(UTC).isoformat(),
        }
    )
    stats = get_pii_stats(request)
    stats["total_reveals"] += 1
    await dispatch_event(
        request,
        VaultRevealRequested(payload={"resource_id": body.placeholder}),
        stream_id="pii",
    )
    return asdict(command)


@router.get("/pii/vault/log")
async def vault_activity_log(request: Request) -> list[dict[str, Any]]:
    """Return the vault reveal activity log."""
    return get_vault_log(request)


@router.get("/pii/stats")
async def pii_stats(request: Request) -> dict[str, int]:
    """Return PII detection/anonymisation statistics."""
    return get_pii_stats(request)
