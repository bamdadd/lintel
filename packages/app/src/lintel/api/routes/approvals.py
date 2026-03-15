"""Approval operation endpoints."""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.types import ThreadRef
from lintel.domain.events import HumanApprovalGranted, HumanApprovalRejected
from lintel.slack.commands import GrantApproval, RejectApproval

router = APIRouter()


class GrantApprovalRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    gate_type: str
    approver_id: str
    approver_name: str


class RejectApprovalRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    gate_type: str
    rejector_id: str
    reason: str


@router.post("/approvals/grant", status_code=200)
async def grant_approval(request: Request, body: GrantApprovalRequest) -> dict[str, Any]:
    """Grant an approval for a workflow gate."""
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    command = GrantApproval(
        thread_ref=thread_ref,
        gate_type=body.gate_type,
        approver_id=body.approver_id,
        approver_name=body.approver_name,
    )
    await dispatch_event(
        request,
        HumanApprovalGranted(payload={"resource_id": body.thread_ts}),
        stream_id="approvals",
    )
    return asdict(command)


@router.post("/approvals/reject", status_code=200)
async def reject_approval(request: Request, body: RejectApprovalRequest) -> dict[str, Any]:
    """Reject an approval for a workflow gate."""
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    command = RejectApproval(
        thread_ref=thread_ref,
        gate_type=body.gate_type,
        rejector_id=body.rejector_id,
        reason=body.reason,
    )
    await dispatch_event(
        request,
        HumanApprovalRejected(payload={"resource_id": body.thread_ts}),
        stream_id="approvals",
    )
    return asdict(command)
