"""Audit response models."""

from typing import Any

from pydantic import BaseModel


class AuditEntryResponse(BaseModel):
    entry_id: str
    actor_id: str
    actor_type: str
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any] | None = None
    timestamp: str = ""
