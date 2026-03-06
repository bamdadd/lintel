"""Admin / danger-zone endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from lintel.api.deps import get_projection_engine
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine

router = APIRouter()


@router.post("/admin/reset-projections")
async def reset_projections(
    engine: Annotated[InMemoryProjectionEngine, Depends(get_projection_engine)],
) -> dict[str, Any]:
    """Reset all projections (danger zone)."""
    await engine.reset_all()
    return {"status": "projections_reset"}
