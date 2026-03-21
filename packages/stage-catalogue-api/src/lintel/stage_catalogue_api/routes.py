"""Stage catalogue routes — GET /stage-types."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.stage_catalogue_api.models import NodeDescriptorResponse
from lintel.workflows.builtins import ensure_builtins_registered
from lintel.workflows.node_registry import node_registry

router = APIRouter()


@router.get("/stage-types", response_model=list[NodeDescriptorResponse])
async def list_stage_types() -> list[NodeDescriptorResponse]:
    """Return all registered workflow stage/node types."""
    ensure_builtins_registered()
    descriptors = node_registry.list_all()
    return [
        NodeDescriptorResponse(
            node_type=d.node_type,
            display_name=d.display_name,
            description=d.description,
            router_type=d.router_type,
            output_edges=list(d.output_edges),
            is_builtin=d.is_builtin,
            tags=list(d.tags),
            metadata=d.metadata,
        )
        for d in descriptors
    ]
