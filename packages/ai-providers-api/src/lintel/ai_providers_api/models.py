"""AI provider model discovery endpoints."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
import httpx

from lintel.ai_providers_api.providers import ai_provider_store_provider, model_store_provider
from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.models.types import AIProvider, AIProviderType

router = APIRouter()


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


@router.get("/ai-providers/{provider_id}/available-models")
async def list_available_models(
    provider_id: str,
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
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


@router.get("/ai-providers/{provider_id}/models")
async def list_provider_models(
    provider_id: str,
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
    m_store: Any = Depends(model_store_provider),  # noqa: B008, ANN401
) -> list[dict[str, Any]]:
    """List all models registered under a specific provider."""
    from dataclasses import asdict

    provider = await store.get(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    models = await m_store.list_by_provider(provider_id)
    results = []
    for m in models:
        d = asdict(m)
        d["capabilities"] = list(m.capabilities)
        d["provider_name"] = provider.name
        d["provider_type"] = provider.provider_type.value
        results.append(d)
    return results
