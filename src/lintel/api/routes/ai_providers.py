"""AI model provider management endpoints."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.contracts.types import AIProvider, AIProviderType

router = APIRouter()


class InMemoryAIProviderStore:
    """In-memory store for AI provider configurations."""

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._api_keys: dict[str, str] = {}

    async def add(self, provider: AIProvider, api_key: str = "") -> None:
        self._providers[provider.provider_id] = provider
        if api_key:
            self._api_keys[provider.provider_id] = api_key

    async def get(self, provider_id: str) -> AIProvider | None:
        return self._providers.get(provider_id)

    async def list_all(self) -> list[AIProvider]:
        return list(self._providers.values())

    async def update(self, provider: AIProvider) -> None:
        if provider.provider_id not in self._providers:
            msg = f"Provider {provider.provider_id} not found"
            raise KeyError(msg)
        self._providers[provider.provider_id] = provider

    async def update_api_key(self, provider_id: str, api_key: str) -> None:
        if provider_id not in self._providers:
            msg = f"Provider {provider_id} not found"
            raise KeyError(msg)
        self._api_keys[provider_id] = api_key

    async def remove(self, provider_id: str) -> None:
        if provider_id not in self._providers:
            msg = f"Provider {provider_id} not found"
            raise KeyError(msg)
        del self._providers[provider_id]
        self._api_keys.pop(provider_id, None)

    async def has_api_key(self, provider_id: str) -> bool:
        return bool(self._api_keys.get(provider_id))

    async def get_default(self) -> AIProvider | None:
        for p in self._providers.values():
            if p.is_default:
                return p
        return None


def get_ai_provider_store(request: Request) -> InMemoryAIProviderStore:
    """Get AI provider store from app state."""
    return request.app.state.ai_provider_store  # type: ignore[no-any-return]


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


class UpdateAPIKeyRequest(BaseModel):
    api_key: str


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.post("/ai-providers", status_code=201)
async def create_ai_provider(
    body: CreateAIProviderRequest,
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    result = asdict(provider)
    result["models"] = list(provider.models)
    result["has_api_key"] = bool(body.api_key)
    if body.api_key:
        result["api_key_preview"] = _mask_key(body.api_key)
    return result


@router.get("/ai-providers")
async def list_ai_providers(
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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


@router.get("/ai-providers/types")
async def list_provider_types() -> list[dict[str, Any]]:
    """List supported AI provider types with their field requirements."""
    results = []
    for t in AIProviderType:
        reqs = PROVIDER_FIELD_REQUIREMENTS.get(t, {})
        results.append({
            "provider_type": t.value,
            "required_fields": reqs.get("required", []),
            "optional_fields": reqs.get("optional", []),
            "hidden_fields": reqs.get("hidden", []),
        })
    return results


@router.get("/ai-providers/default")
async def get_default_provider(
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    d = asdict(updated)
    d["models"] = list(updated.models)
    d["has_api_key"] = await store.has_api_key(provider_id)
    return d


@router.put("/ai-providers/{provider_id}/api-key")
async def update_api_key(
    provider_id: str,
    body: UpdateAPIKeyRequest,
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
) -> dict[str, Any]:
    """Update or set the API key for a provider."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    await store.update_api_key(provider_id, body.api_key)
    return {
        "provider_id": provider_id,
        "api_key_preview": _mask_key(body.api_key),
        "status": "updated",
    }


@router.delete("/ai-providers/{provider_id}", status_code=204)
async def delete_ai_provider(
    provider_id: str,
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
) -> None:
    """Remove an AI provider."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    await store.remove(provider_id)


@router.get("/ai-providers/{provider_id}/models")
async def list_provider_models(
    provider_id: str,
    store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
    request: Request,
) -> list[dict[str, Any]]:
    """List all models registered under a specific provider."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    from lintel.api.routes.models import get_model_store

    model_store = get_model_store(request)
    models = await model_store.list_by_provider(provider_id)
    results = []
    for m in models:
        d = asdict(m)
        d["capabilities"] = list(m.capabilities)
        d["provider_name"] = provider.name
        d["provider_type"] = provider.provider_type.value
        results.append(d)
    return results
