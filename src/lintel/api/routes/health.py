"""Health check endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.api.schemas.health import HealthResponse, PingResponse

router = APIRouter()


@router.get("/healthz", response_model=HealthResponse)
async def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}


@router.get("/ping", response_model=PingResponse)
async def ping() -> dict[str, str]:
    """Ping / readiness check — returns pong."""
    return {"status": "pong"}
