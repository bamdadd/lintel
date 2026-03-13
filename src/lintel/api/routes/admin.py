"""Admin / danger-zone endpoints."""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Request

from lintel.api.deps import get_projection_engine
from lintel.infrastructure.projections.engine import InMemoryProjectionEngine

logger = structlog.get_logger()

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


@router.post("/admin/refresh-claude-credentials")
async def refresh_claude_credentials(request: Request) -> dict[str, Any]:
    """Read Claude Code credentials from host and inject into all running sandboxes.

    On macOS reads from Keychain, on Linux reads from ~/.claude/.credentials.json.
    """
    from lintel.infrastructure.models.claude_code import (
        _inject_credentials_into_sandbox,
        _read_host_credentials,
        _validate_credentials_json,
    )

    sandbox_manager = getattr(request.app.state, "sandbox_manager", None)
    sandbox_store = getattr(request.app.state, "sandbox_store", None)
    if sandbox_manager is None or sandbox_store is None:
        return {"status": "error", "detail": "sandbox infrastructure not available"}

    creds_json = _read_host_credentials()
    if not creds_json:
        return {"status": "error", "detail": "no credentials found on host"}

    if not _validate_credentials_json(creds_json):
        return {"status": "error", "detail": "host credentials are expired"}

    sandboxes = await sandbox_store.list_all()
    results: dict[str, str] = {}
    for sb in sandboxes:
        sid = sb.get("sandbox_id", "")
        if not sid:
            continue
        ok = await _inject_credentials_into_sandbox(sandbox_manager, sid, creds_json)
        results[sid] = "refreshed" if ok else "failed"
        logger.info("claude_creds_refresh", sandbox_id=sid[:12], result=results[sid])

    return {
        "status": "ok",
        "sandboxes_refreshed": sum(1 for v in results.values() if v == "refreshed"),
        "sandboxes_failed": sum(1 for v in results.values() if v == "failed"),
        "details": results,
    }


@router.get("/admin/claude-credentials-status")
async def claude_credentials_status(request: Request) -> dict[str, Any]:
    """Check Claude Code credential expiry. Only reports if claude_code is configured as a provider.

    Returns token status, expiry time, and minutes remaining. The UI can poll this
    to show a warning banner when credentials are about to expire.
    """
    import json as _json
    from datetime import UTC, datetime

    from lintel.contracts.types import AIProviderType
    from lintel.infrastructure.models.claude_code import _read_host_credentials

    # Check if any AI provider is claude_code
    ai_store = getattr(request.app.state, "ai_provider_store", None)
    if ai_store is None:
        return {"configured": False}

    providers = await ai_store.list_all()
    has_claude_code = any(
        getattr(p, "provider_type", None) == AIProviderType.CLAUDE_CODE for p in providers
    )
    if not has_claude_code:
        return {"configured": False}

    creds_json = _read_host_credentials()
    if not creds_json:
        return {
            "configured": True,
            "status": "missing",
            "detail": "No credentials found on host",
        }

    try:
        creds = _json.loads(creds_json)
    except (ValueError, _json.JSONDecodeError):
        return {
            "configured": True,
            "status": "invalid",
            "detail": "Cannot parse credentials",
        }

    expires_at = creds.get("claudeAiOauth", {}).get("expiresAt")
    if not expires_at:
        return {
            "configured": True,
            "status": "valid",
            "detail": "No expiry field — assuming valid",
        }

    if isinstance(expires_at, str):
        exp_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    else:
        exp_dt = datetime.fromtimestamp(expires_at / 1000, tz=UTC)

    now = datetime.now(tz=UTC)
    minutes_remaining = int((exp_dt - now).total_seconds() / 60)

    if now >= exp_dt:
        return {
            "configured": True,
            "status": "expired",
            "expires_at": exp_dt.isoformat(),
            "minutes_remaining": 0,
        }

    return {
        "configured": True,
        "status": "valid",
        "expires_at": exp_dt.isoformat(),
        "minutes_remaining": minutes_remaining,
    }
