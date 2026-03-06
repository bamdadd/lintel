"""Metrics and statistics endpoints."""

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


def get_agent_activity(request: Request) -> list[dict[str, Any]]:
    """Get agent activity log from app state."""
    if not hasattr(request.app.state, "agent_activity"):
        request.app.state.agent_activity = []
    return request.app.state.agent_activity  # type: ignore[no-any-return]


@router.get("/metrics/pii")
async def pii_metrics(request: Request) -> dict[str, Any]:
    """PII detection/anonymisation stats over time."""
    if not hasattr(request.app.state, "pii_stats"):
        request.app.state.pii_stats = {
            "total_scanned": 0,
            "total_detected": 0,
            "total_anonymised": 0,
            "total_blocked": 0,
            "total_reveals": 0,
        }
    return {
        "pii": request.app.state.pii_stats,
    }


@router.get("/metrics/agents")
async def agent_metrics(request: Request) -> dict[str, Any]:
    """Agent activity statistics."""
    activity = get_agent_activity(request)
    return {
        "total_steps": len(activity),
        "activity": activity[-100:],  # last 100 entries
    }


@router.get("/metrics/overview")
async def overview_metrics(request: Request) -> dict[str, Any]:
    """Combined overview metrics for the dashboard."""
    pii_stats: dict[str, int] = getattr(
        request.app.state,
        "pii_stats",
        {
            "total_scanned": 0,
            "total_detected": 0,
            "total_anonymised": 0,
            "total_blocked": 0,
            "total_reveals": 0,
        },
    )
    sandbox_registry: dict[str, Any] = getattr(request.app.state, "sandbox_registry", {})
    connections: dict[str, Any] = getattr(request.app.state, "connections", {})
    return {
        "pii": pii_stats,
        "sandboxes": {"total": len(sandbox_registry)},
        "connections": {"total": len(connections)},
    }
