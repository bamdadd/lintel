"""AI model provider management endpoints — barrel module."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.ai_providers_api.api_keys import (
    UpdateAPIKeyRequest,
)
from lintel.ai_providers_api.api_keys import (
    router as api_keys_router,
)
from lintel.ai_providers_api.models import router as models_router
from lintel.ai_providers_api.providers import (
    PROVIDER_FIELD_REQUIREMENTS,
    CreateAIProviderRequest,
    UpdateAIProviderRequest,
    _mask_key,
    ai_provider_store_provider,
    model_store_provider,
)
from lintel.ai_providers_api.providers import (
    router as providers_router,
)

# Re-export for backward compatibility
__all__ = [
    "PROVIDER_FIELD_REQUIREMENTS",
    "CreateAIProviderRequest",
    "UpdateAIProviderRequest",
    "UpdateAPIKeyRequest",
    "_mask_key",
    "ai_provider_store_provider",
    "model_store_provider",
    "router",
]

router = APIRouter()
# NOTE: models router must be included before providers router so that
# fixed-path routes like /ai-providers/types and /ai-providers/default
# are registered before the parameterised /ai-providers/{provider_id} routes.
router.include_router(models_router)
router.include_router(providers_router)
router.include_router(api_keys_router)
