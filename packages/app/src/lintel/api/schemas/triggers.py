"""Trigger response models."""

from typing import Any

from pydantic import BaseModel


class TriggerResponse(BaseModel):
    trigger_id: str
    project_id: str
    trigger_type: str
    name: str
    config: dict[str, Any] | None = None
    enabled: bool = True
