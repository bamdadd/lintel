"""Response models for the stage catalogue API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class NodeDescriptorResponse(BaseModel):
    """API response model for a single node/stage type."""

    model_config = ConfigDict(from_attributes=True)

    node_type: str
    display_name: str
    description: str = ""
    router_type: str | None = None
    output_edges: list[str] = []
    is_builtin: bool = True
    tags: list[str] = []
    metadata: dict[str, str] = {}
