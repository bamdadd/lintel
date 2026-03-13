"""Workflow definition response models."""

from typing import Any

from pydantic import BaseModel


class WorkflowDefinitionResponse(BaseModel):
    definition_id: str
    name: str
    description: str = ""
    is_template: bool = False
    graph: dict[str, Any] = {}
    created_at: str = ""
    updated_at: str = ""
