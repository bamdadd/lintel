"""Admin / danger-zone endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

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


@router.get("/admin/cache-stats")
async def get_cache_stats(request: Request) -> dict[str, int]:
    """Return model router cache hit/miss statistics."""
    model_router = getattr(request.app.state, "model_router", None)
    if model_router is None:
        return {"hits": 0, "misses": 0, "size": 0}
    return model_router.cache_stats  # type: ignore[no-any-return]


@router.post("/admin/cache-clear")
async def clear_cache(request: Request) -> dict[str, str]:
    """Flush the model router response cache."""
    model_router = getattr(request.app.state, "model_router", None)
    if model_router is not None and hasattr(model_router, "_response_cache"):
        model_router._response_cache.clear()
        model_router._cache_hits = 0
        model_router._cache_misses = 0
    return {"status": "cache_cleared"}
