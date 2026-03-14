"""AI model provider management endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request
import httpx
from pydantic import BaseModel, Field

from lintel.api.container import AppContainer
from lintel.contracts.events import (
    AIProviderApiKeyUpdated,
    AIProviderCreated,
    AIProviderRemoved,
    AIProviderUpdated,
)
from lintel.contracts.types import AIProvider, AIProviderType
from lintel.domain.event_dispatcher import dispatch_event

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


class UpdateAPIKeyRequest(BaseModel):
    api_key: str


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


@router.post("/ai-providers", status_code=201)
@inject
async def create_ai_provider(
    body: CreateAIProviderRequest,
    request: Request,
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
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
@inject
async def list_ai_providers(
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
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
        results.append(
            {
                "provider_type": t.value,
                "required_fields": reqs.get("required", []),
                "optional_fields": reqs.get("optional", []),
                "hidden_fields": reqs.get("hidden", []),
            }
        )
    return results


@router.get("/ai-providers/default")
@inject
async def get_default_provider(
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
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
@inject
async def get_ai_provider(
    provider_id: str,
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
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
@inject
async def update_ai_provider(
    provider_id: str,
    body: UpdateAIProviderRequest,
    request: Request,
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
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
    d = asdict(updated)
    d["models"] = list(updated.models)
    d["has_api_key"] = await store.has_api_key(provider_id)
    return d


@router.put("/ai-providers/{provider_id}/api-key")
@inject
async def update_api_key(
    provider_id: str,
    body: UpdateAPIKeyRequest,
    request: Request,
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
) -> dict[str, Any]:
    """Update or set the API key for a provider."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    await store.update_api_key(provider_id, body.api_key)
    await dispatch_event(
        request,
        AIProviderApiKeyUpdated(payload={"resource_id": provider_id}),
        stream_id=f"ai_provider:{provider_id}",
    )
    return {
        "provider_id": provider_id,
        "api_key_preview": _mask_key(body.api_key),
        "status": "updated",
    }


@router.delete("/ai-providers/{provider_id}", status_code=204)
@inject
async def delete_ai_provider(
    provider_id: str,
    request: Request,
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
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


OLLAMA_MODEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "llama3.2": {"max_tokens": 2048, "temperature": 0.7},
    "llama3.1": {"max_tokens": 4096, "temperature": 0.7},
    "llama3": {"max_tokens": 4096, "temperature": 0.7},
    "mistral": {"max_tokens": 4096, "temperature": 0.7},
    "mixtral": {"max_tokens": 4096, "temperature": 0.7},
    "codellama": {"max_tokens": 4096, "temperature": 0.2},
    "deepseek-coder": {"max_tokens": 4096, "temperature": 0.2},
    "phi3": {"max_tokens": 4096, "temperature": 0.7},
    "gemma2": {"max_tokens": 8192, "temperature": 0.7},
    "qwen2.5-coder": {"max_tokens": 8192, "temperature": 0.2},
}


def _ollama_model_defaults(model_name: str) -> dict[str, Any]:
    """Get sensible defaults for an Ollama model based on its name."""
    base = model_name.split(":")[0].lower()
    if base in OLLAMA_MODEL_DEFAULTS:
        return OLLAMA_MODEL_DEFAULTS[base]
    if "code" in base or "coder" in base:
        return {"max_tokens": 4096, "temperature": 0.2}
    return {"max_tokens": 4096, "temperature": 0.7}


@router.get("/ai-providers/{provider_id}/available-models")
@inject
async def list_available_models(
    provider_id: str,
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    """Query the provider for available models (e.g. Ollama /api/tags)."""
    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")

    if provider.provider_type == AIProviderType.BEDROCK:
        return await _list_bedrock_models(provider)

    if provider.provider_type != AIProviderType.OLLAMA:
        raise HTTPException(
            status_code=400,
            detail=f"Model discovery is only supported for ollama and bedrock providers,"
            f" got {provider.provider_type.value}",
        )

    api_base = provider.api_base.rstrip("/")
    if not api_base:
        raise HTTPException(status_code=400, detail="Provider has no api_base configured")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{api_base}/api/tags")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to connect to Ollama at {api_base}: {exc}",
        ) from exc

    results = []
    for model in data.get("models", []):
        name = model.get("name", "")
        details = model.get("details", {})
        defaults = _ollama_model_defaults(name)
        results.append(
            {
                "model_name": name,
                "display_name": name.split(":")[0].replace("-", " ").title(),
                "family": details.get("family", ""),
                "parameter_size": details.get("parameter_size", ""),
                "quantization_level": details.get("quantization_level", ""),
                "format": details.get("format", ""),
                "size_bytes": model.get("size", 0),
                "max_tokens": defaults["max_tokens"],
                "temperature": defaults["temperature"],
            }
        )
    return results


BEDROCK_MODEL_DEFAULTS: dict[str, dict[str, Any]] = {
    "claude-sonnet-4": {"max_tokens": 8192, "temperature": 0.0},
    "claude-haiku-4": {"max_tokens": 8192, "temperature": 0.0},
    "claude-3-5-sonnet": {"max_tokens": 8192, "temperature": 0.0},
    "claude-3-5-haiku": {"max_tokens": 8192, "temperature": 0.0},
    "claude-3-sonnet": {"max_tokens": 4096, "temperature": 0.0},
    "claude-3-haiku": {"max_tokens": 4096, "temperature": 0.0},
    "claude-3-opus": {"max_tokens": 4096, "temperature": 0.0},
}


def _bedrock_model_defaults(model_id: str) -> dict[str, Any]:
    """Get sensible defaults for a Bedrock model."""
    for key, defaults in BEDROCK_MODEL_DEFAULTS.items():
        if key in model_id:
            return defaults
    return {"max_tokens": 4096, "temperature": 0.0}


async def _list_bedrock_models(provider: AIProvider) -> list[dict[str, Any]]:
    """List available foundation models from AWS Bedrock."""
    import asyncio

    import boto3  # type: ignore[import-untyped]

    config = provider.config or {}
    region = config.get("aws_region_name", "us-east-1")
    profile = config.get("aws_profile_name")

    def _fetch() -> list[dict[str, Any]]:
        session = boto3.Session(profile_name=profile, region_name=str(region))
        client = session.client("bedrock")
        results: list[dict[str, Any]] = []

        # List cross-region inference profiles (eu.*, us.*, ap.* prefixed models)
        try:
            profiles_resp = client.list_inference_profiles()
            for profile_info in profiles_resp.get("inferenceProfileSummaries", []):
                profile_id = profile_info.get("inferenceProfileId", "")
                profile_name = profile_info.get("inferenceProfileName", profile_id)
                defaults = _bedrock_model_defaults(profile_id)
                results.append(
                    {
                        "model_name": profile_id,
                        "display_name": f"{profile_name} (cross-region)",
                        "family": "Cross-Region",
                        "parameter_size": "",
                        "quantization_level": "",
                        "format": "",
                        "size_bytes": 0,
                        "max_tokens": defaults["max_tokens"],
                        "temperature": defaults["temperature"],
                    }
                )
        except Exception:
            pass  # Inference profiles API may not be available in all regions

        # List foundation models
        response = client.list_foundation_models(
            byOutputModality="TEXT",
        )
        for model in response.get("modelSummaries", []):
            model_id = model.get("modelId", "")
            model_name = model.get("modelName", model_id)
            provider_name = model.get("providerName", "")
            defaults = _bedrock_model_defaults(model_id)
            results.append(
                {
                    "model_name": model_id,
                    "display_name": model_name,
                    "family": provider_name,
                    "parameter_size": "",
                    "quantization_level": "",
                    "format": "",
                    "size_bytes": 0,
                    "max_tokens": defaults["max_tokens"],
                    "temperature": defaults["temperature"],
                }
            )
        return results

    try:
        return await asyncio.to_thread(_fetch)
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to list Bedrock models: {exc}",
        ) from exc


@router.get("/ai-providers/{provider_id}/models")
@inject
async def list_provider_models(
    provider_id: str,
    request: Request,
    store: InMemoryAIProviderStore = Depends(Provide[AppContainer.ai_provider_store]),  # noqa: B008
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
