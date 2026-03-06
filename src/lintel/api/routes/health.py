"""Health check endpoint."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, Any]:
    """Liveness probe."""
    return {"status": "ok"}
