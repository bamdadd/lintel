"""Approval request CRUD and action endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.approval_requests_api.store import InMemoryApprovalRequestStore
from lintel.domain.events import (
    ApprovalRequestApproved,
    ApprovalRequestCreated,
    ApprovalRequestRejected,
)
from lintel.domain.types import ApprovalRequest, ApprovalStatus

router = APIRouter()

approval_request_store_provider: StoreProvider = StoreProvider()


class CreateApprovalRequestBody(BaseModel):
    approval_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    gate_type: str
    requested_by: str = ""
    expires_at: str = ""


class DecisionBody(BaseModel):
    decided_by: str


class RejectBody(BaseModel):
    decided_by: str
    reason: str = ""


@router.post("/approval-requests", status_code=201)
async def create_approval_request(
    body: CreateApprovalRequestBody,
    request: Request,
    store: InMemoryApprovalRequestStore = Depends(approval_request_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.approval_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Approval request already exists")
    approval = ApprovalRequest(
        approval_id=body.approval_id,
        run_id=body.run_id,
        gate_type=body.gate_type,
        requested_by=body.requested_by,
        expires_at=body.expires_at,
    )
    await store.add(approval)
    await dispatch_event(
        request,
        ApprovalRequestCreated(payload={"resource_id": approval.approval_id}),
        stream_id=f"approval_request:{approval.approval_id}",
    )
    return asdict(approval)


@router.get("/approval-requests")
async def list_approval_requests(
    store: InMemoryApprovalRequestStore = Depends(approval_request_store_provider),  # noqa: B008
    run_id: str | None = None,
    status: ApprovalStatus | None = None,
) -> list[dict[str, Any]]:
    items = await store.list_all()
    if run_id is not None:
        items = [a for a in items if a.run_id == run_id]
    if status is not None:
        items = [a for a in items if a.status == status]
    return [asdict(a) for a in items]


@router.get("/approval-requests/pending")
async def list_pending_approval_requests(
    store: InMemoryApprovalRequestStore = Depends(approval_request_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    items = await store.list_all()
    return [asdict(a) for a in items if a.status == ApprovalStatus.PENDING]


@router.get("/approval-requests/{approval_id}")
async def get_approval_request(
    approval_id: str,
    store: InMemoryApprovalRequestStore = Depends(approval_request_store_provider),  # noqa: B008
) -> dict[str, Any]:
    approval = await store.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    return asdict(approval)


@router.post("/approval-requests/{approval_id}/approve")
async def approve_approval_request(
    approval_id: str,
    body: DecisionBody,
    request: Request,
    store: InMemoryApprovalRequestStore = Depends(approval_request_store_provider),  # noqa: B008
) -> dict[str, Any]:
    approval = await store.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot approve: status is {approval.status}",
        )
    updated = ApprovalRequest(
        **{
            **asdict(approval),
            "status": ApprovalStatus.APPROVED,
            "decided_by": body.decided_by,
        }
    )
    await store.update(updated)
    await dispatch_event(
        request,
        ApprovalRequestApproved(payload={"resource_id": approval_id}),
        stream_id=f"approval_request:{approval_id}",
    )
    return asdict(updated)


@router.post("/approval-requests/{approval_id}/reject")
async def reject_approval_request(
    approval_id: str,
    body: RejectBody,
    request: Request,
    store: InMemoryApprovalRequestStore = Depends(approval_request_store_provider),  # noqa: B008
) -> dict[str, Any]:
    approval = await store.get(approval_id)
    if approval is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if approval.status != ApprovalStatus.PENDING:
        raise HTTPException(
            status_code=409,
            detail=f"Cannot reject: status is {approval.status}",
        )
    updated = ApprovalRequest(
        **{
            **asdict(approval),
            "status": ApprovalStatus.REJECTED,
            "decided_by": body.decided_by,
            "reason": body.reason,
        }
    )
    await store.update(updated)
    await dispatch_event(
        request,
        ApprovalRequestRejected(payload={"resource_id": approval_id}),
        stream_id=f"approval_request:{approval_id}",
    )
    return asdict(updated)
