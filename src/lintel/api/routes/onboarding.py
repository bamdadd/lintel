"""Onboarding status endpoint."""

from typing import Any

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/onboarding/status")
async def get_onboarding_status(request: Request) -> dict[str, Any]:
    """Check which onboarding steps have been completed."""
    ai_provider_store = request.app.state.ai_provider_store
    repo_store = request.app.state.repository_store

    providers = await ai_provider_store.list_all()
    repos = await repo_store.list_all()

    connections: list[dict[str, Any]] = []
    if hasattr(request.app.state, "connections"):
        connections = list(request.app.state.connections.values())

    has_chat = any(c.get("connection_type") == "slack" for c in connections)
    has_ai_provider = len(providers) > 0
    has_repo = len(repos) > 0
    is_complete = has_ai_provider and has_repo

    return {
        "has_ai_provider": has_ai_provider,
        "has_repo": has_repo,
        "has_chat": has_chat,
        "is_complete": is_complete,
        "providers_count": len(providers),
        "repos_count": len(repos),
    }
