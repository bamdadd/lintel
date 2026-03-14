"""Settings response models."""

from typing import Any

from pydantic import BaseModel


class ConnectionResponse(BaseModel):
    connection_id: str
    connection_type: str
    name: str
    config: dict[str, Any] = {}
    status: str = "untested"


class ConnectionTestResponse(BaseModel):
    connection_id: str
    status: str
    message: str


class SettingsResponse(BaseModel):
    workspace_name: str
    default_model_provider: str
    pii_detection_enabled: bool
    sandbox_enabled: bool
    max_concurrent_workflows: int
    max_sandboxes: int
