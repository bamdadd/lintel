"""AI provider API key endpoint: update API key."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.ai_providers_api.providers import ai_provider_store_provider
from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.api_support.event_dispatcher import dispatch_event
from lintel.models.events import AIProviderApiKeyUpdated

router = APIRouter()


def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "****"
    return key[:4] + "****" + key[-4:]


class UpdateAPIKeyRequest(BaseModel):
    api_key: str


@router.put("/ai-providers/{provider_id}/api-key")
async def update_api_key(
    provider_id: str,
    body: UpdateAPIKeyRequest,
    request: Request,
    store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
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
