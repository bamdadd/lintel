"""AI provider CRUD endpoints: create, list, get, update, delete, get default."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.models.events import (
    AIProviderCreated,
    AIProviderRemoved,
    AIProviderUpdated,
)
from lintel.models.types import AIProvider, AIProviderType

router = APIRouter()

ai_provider_store_provider: StoreProvider = StoreProvider()
model_store_provider: StoreProvider = StoreProvider()


PROVIDER_FIELD_REQUIREMENTS: dict[AIProviderType, dict[str, Any]] = {
    AIProviderType.OLLAMA: {
        "required": ["api_base"],
        "optional": ["config"],
        "hidden": ["api_key"],
    },
    AIProviderType.ANTHROPIC: {
        "required": ["api_key"],
        "optional": ["api_base", "config"],
        "hidden": [],
    },
    AIProviderType.OPENAI: {
        "required": ["api_key"],
        "optional": ["api_base", "config"],
        "hidden": [],
    },
    AIProviderType.AZURE_OPENAI: {
        "required": ["api_key", "api_base"],
        "optional": ["config"],
        "hidden": [],
    },
    AIProviderType.GOOGLE: {
        "required": ["api_key"],
        "optional": ["api_base", "config"],
        "hidden": [],
    },
    AIProviderType.BEDROCK: {
        "required": [],
        "optional": ["api_base", "config"],
        "hidden": ["api_key"],
    },
    AIProviderType.CUSTOM: {
        "required": ["api_base"],
        "optional": ["api_key", "config"],
        "hidden": [],
    },
    AIProviderType.CLAUDE_CODE: {
        "required": [],
        "optional": ["config"],
        "hidden": ["api_key", "api_base"],
    },
}


class CreateAIProviderRequest(BaseModel):
    provider_id: str = Field(default_factory=lambda: str(uuid4()))
    provider_type: AIProviderType
    name: str
    api_key: str = ""
    api_base: str = ""
    is_default: bool = False
    config: dict[str, Any] = {}


class UpdateAIProviderRequest(BaseModel):
    name: str | None = None
    api_base: str | None = None
    is_default: bool | None = None
    config: dict[str, Any] | None = None


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.post("/ai-providers", status_code=201)
async def create_ai_provider(
    body: CreateAIProviderRequest,
    request: Request,
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Register an AI model provider."""
    reqs = PROVIDER_FIELD_REQUIREMENTS.get(body.provider_type, {})
    hidden = reqs.get("hidden", [])
    required = reqs.get("required", [])
    if "api_key" in required and not body.api_key:
        raise HTTPException(
            status_code=422,
            detail=f"api_key is required for {body.provider_type.value} providers",
        )
    if "api_base" in required and not body.api_base:
        raise HTTPException(
            status_code=422,
            detail=f"api_base is required for {body.provider_type.value} providers",
        )
    if "api_key" in hidden and body.api_key:
        raise HTTPException(
            status_code=422,
            detail=f"api_key is not used for {body.provider_type.value} providers",
        )
    existing = await store.get(body.provider_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Provider already exists")
    provider = AIProvider(
        provider_id=body.provider_id,
        provider_type=body.provider_type,
        name=body.name,
        api_base=body.api_base,
        is_default=body.is_default,
        config=body.config or None,
    )
    await store.add(provider, api_key=body.api_key)
    await dispatch_event(
        request,
        AIProviderCreated(payload={"resource_id": body.provider_id, "name": body.name}),
        stream_id=f"ai_provider:{body.provider_id}",
    )
    result = asdict(provider)
    result["models"] = list(provider.models)
    result["has_api_key"] = bool(body.api_key)
    if body.api_key:
        result["api_key_preview"] = _mask_key(body.api_key)
    return result


@router.get("/ai-providers")
async def list_ai_providers(
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all configured AI providers."""
    providers = await store.list_all()
    results = []
    for p in providers:
        d = asdict(p)
        d["models"] = list(p.models)
        d["has_api_key"] = await store.has_api_key(p.provider_id)
        results.append(d)
    return results


@router.get("/ai-providers/default")
async def get_default_provider(
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get the default AI provider."""
    provider = await store.get_default()
    if provider is None:
        raise HTTPException(status_code=404, detail="No default provider set")
    d = asdict(provider)
    d["models"] = list(provider.models)
    d["has_api_key"] = await store.has_api_key(provider.provider_id)
    return d


@router.get("/ai-providers/{provider_id}")
async def get_ai_provider(
    provider_id: str,
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific AI provider."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    d = asdict(provider)
    d["models"] = list(provider.models)
    d["has_api_key"] = await store.has_api_key(provider_id)
    return d


@router.patch("/ai-providers/{provider_id}")
async def update_ai_provider(
    provider_id: str,
    body: UpdateAIProviderRequest,
    request: Request,
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Update an AI provider's configuration."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    current = asdict(provider)
    updates = body.model_dump(exclude_none=True)
    merged = {**current, **updates}
    updated = AIProvider(**merged)
    await store.update(updated)
    await dispatch_event(
        request,
        AIProviderUpdated(payload={"resource_id": provider_id, "fields": list(updates.keys())}),
        stream_id=f"ai_provider:{provider_id}",
    )
    # Invalidate model router default cache when default provider changes
    if "is_default" in updates:
        model_router = getattr(request.app.state, "model_router", None)
        if model_router is not None and hasattr(model_router, "_cached_default"):
            model_router._cached_default = None
    d = asdict(updated)
    d["models"] = list(updated.models)
    d["has_api_key"] = await store.has_api_key(provider_id)
    return d


@router.delete("/ai-providers/{provider_id}", status_code=204)
async def delete_ai_provider(
    provider_id: str,
    request: Request,
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> None:
    """Remove an AI provider."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    await store.remove(provider_id)
    await dispatch_event(
        request,
        AIProviderRemoved(payload={"resource_id": provider_id}),
        stream_id=f"ai_provider:{provider_id}",
    )
