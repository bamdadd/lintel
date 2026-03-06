"""Approval request response models."""

from pydantic import BaseModel


class ApprovalRequestResponse(BaseModel):
    approval_id: str
    run_id: str
    gate_type: str
    status: str = "pending"
    requested_by: str = ""
    decided_by: str = ""
    reason: str = ""
    expires_at: str = ""
