"""Secret rotation and expiry management endpoints."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.secret_rotation_api.store import (
        InMemoryExpiryTracker,
        InMemoryRotationHistoryStore,
        InMemoryRotationPolicyStore,
    )

router = APIRouter()

rotation_policy_store_provider: StoreProvider[InMemoryRotationPolicyStore] = StoreProvider()
rotation_history_store_provider: StoreProvider[InMemoryRotationHistoryStore] = StoreProvider()
expiry_tracker_provider: StoreProvider[InMemoryExpiryTracker] = StoreProvider()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateRotationPolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    credential_id: str
    rotation_interval_days: int = Field(ge=1, le=365)
    alert_before_days: int = Field(default=7, ge=1, le=90)
    auto_rotate: bool = False
    description: str = ""


class RotateCredentialRequest(BaseModel):
    rotated_by: str = "system"
    new_expires_at: str | None = None


# ---------------------------------------------------------------------------
# Rotation policy CRUD
# ---------------------------------------------------------------------------


@router.post("/secrets/rotation-policies", status_code=201)
async def create_rotation_policy(
    body: CreateRotationPolicyRequest,
    policy_store: InMemoryRotationPolicyStore = Depends(rotation_policy_store_provider),  # noqa: B008
    expiry_tracker: InMemoryExpiryTracker = Depends(expiry_tracker_provider),  # noqa: B008
) -> dict[str, Any]:
    """Create a rotation policy for a credential."""
    existing = await policy_store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Policy already exists")
    now = datetime.now(tz=UTC)
    expires_at = now + timedelta(days=body.rotation_interval_days)
    data: dict[str, object] = {
        "policy_id": body.policy_id,
        "credential_id": body.credential_id,
        "rotation_interval_days": body.rotation_interval_days,
        "alert_before_days": body.alert_before_days,
        "auto_rotate": body.auto_rotate,
        "description": body.description,
        "created_at": now.isoformat(),
        "next_rotation_at": expires_at.isoformat(),
    }
    result = await policy_store.create(data)
    await expiry_tracker.set_expiry(
        credential_id=body.credential_id,
        expires_at=expires_at.isoformat(),
        policy_id=body.policy_id,
    )
    return dict(result)


@router.get("/secrets/rotation-policies")
async def list_rotation_policies(
    policy_store: InMemoryRotationPolicyStore = Depends(rotation_policy_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all rotation policies."""
    policies = await policy_store.list_all()
    return [dict(p) for p in policies]


@router.get("/secrets/rotation-policies/{policy_id}")
async def get_rotation_policy(
    policy_id: str,
    policy_store: InMemoryRotationPolicyStore = Depends(rotation_policy_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a rotation policy by ID."""
    policy = await policy_store.get(policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Rotation policy not found")
    return dict(policy)


@router.delete("/secrets/rotation-policies/{policy_id}", status_code=204)
async def delete_rotation_policy(
    policy_id: str,
    policy_store: InMemoryRotationPolicyStore = Depends(rotation_policy_store_provider),  # noqa: B008
) -> None:
    """Delete a rotation policy."""
    removed = await policy_store.delete(policy_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Rotation policy not found")


# ---------------------------------------------------------------------------
# Rotate credential
# ---------------------------------------------------------------------------


@router.post("/secrets/rotate/{credential_id}", status_code=201)
async def rotate_credential(
    credential_id: str,
    body: RotateCredentialRequest,
    policy_store: InMemoryRotationPolicyStore = Depends(rotation_policy_store_provider),  # noqa: B008
    history_store: InMemoryRotationHistoryStore = Depends(rotation_history_store_provider),  # noqa: B008
    expiry_tracker: InMemoryExpiryTracker = Depends(expiry_tracker_provider),  # noqa: B008
) -> dict[str, Any]:
    """Record a credential rotation and update expiry."""
    now = datetime.now(tz=UTC)
    # Find matching policy to compute next expiry
    policies = await policy_store.list_all()
    matching = [p for p in policies if p.get("credential_id") == credential_id]
    if matching:
        interval = int(str(matching[0].get("rotation_interval_days", 90)))
        next_expires = now + timedelta(days=interval)
    else:
        next_expires = now + timedelta(days=90)  # default 90 days

    next_expires_iso = body.new_expires_at or next_expires.isoformat()

    entry: dict[str, object] = {
        "entry_id": str(uuid4()),
        "credential_id": credential_id,
        "rotated_at": now.isoformat(),
        "rotated_by": body.rotated_by,
        "new_expires_at": next_expires_iso,
    }
    result = await history_store.record(entry)

    await expiry_tracker.set_expiry(
        credential_id=credential_id,
        expires_at=next_expires_iso,
        policy_id=str(matching[0]["policy_id"]) if matching else None,
    )

    return dict(result)


# ---------------------------------------------------------------------------
# Rotation history
# ---------------------------------------------------------------------------


@router.get("/secrets/rotation-history/{credential_id}")
async def get_rotation_history(
    credential_id: str,
    history_store: InMemoryRotationHistoryStore = Depends(rotation_history_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """Get rotation history for a credential."""
    entries = await history_store.list_by_credential(credential_id)
    return [dict(e) for e in entries]


# ---------------------------------------------------------------------------
# Expiring credentials
# ---------------------------------------------------------------------------


@router.get("/secrets/expiring")
async def list_expiring_credentials(
    days: int = 30,
    expiry_tracker: InMemoryExpiryTracker = Depends(expiry_tracker_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List credentials expiring within the given number of days."""
    cutoff = datetime.now(tz=UTC) + timedelta(days=days)
    entries = await expiry_tracker.list_expiring_before(cutoff.isoformat())
    return [dict(e) for e in entries]
