"""Policy response models."""

from pydantic import BaseModel


class PolicyResponse(BaseModel):
    policy_id: str
    name: str
    event_type: str = ""
    condition: str = ""
    action: str = "require_approval"
    approvers: list[str] = []
    project_id: str = ""
