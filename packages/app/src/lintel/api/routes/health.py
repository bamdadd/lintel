"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.api.schemas.health import HealthResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    """Liveness probe (alias)."""
    return {"status": "ok"}
