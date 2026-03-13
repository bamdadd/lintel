"""Environment response models."""

from typing import Any

from pydantic import BaseModel


class EnvironmentResponse(BaseModel):
    environment_id: str
    name: str
    env_type: str = "development"
    project_id: str = ""
    config: dict[str, Any] | None = None
