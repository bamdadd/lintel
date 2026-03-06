"""Approval operation endpoints."""

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from lintel.contracts.commands import GrantApproval, RejectApproval
from lintel.contracts.types import ThreadRef

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
async def grant_approval(body: GrantApprovalRequest) -> dict[str, Any]:
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
    return asdict(command)


@router.post("/approvals/reject", status_code=200)
async def reject_approval(body: RejectApprovalRequest) -> dict[str, Any]:
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
    return asdict(command)
