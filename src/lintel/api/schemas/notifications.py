"""Notification response models."""

from pydantic import BaseModel


class NotificationRuleResponse(BaseModel):
    rule_id: str
    project_id: str
    event_types: list[str] = []
    channel: str = "slack"
    target: str = ""
    enabled: bool = True
