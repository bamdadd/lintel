"""Approval command response models."""

from pydantic import BaseModel


class ApprovalCommandResponse(BaseModel):
    model_config = {"extra": "allow"}

    thread_ref: dict[str, str] = {}
    gate_type: str = ""
