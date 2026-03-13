"""AI provider response models."""

from typing import Any

from pydantic import BaseModel


class AIProviderResponse(BaseModel):
    provider_id: str
    provider_type: str
    name: str
    api_base: str = ""
    is_default: bool = False
    config: dict[str, Any] | None = None
    has_api_key: bool = False
    api_key_preview: str = ""


class ProviderTypeInfo(BaseModel):
    provider_type: str
    required_fields: list[str] = []
    optional_fields: list[str] = []
    hidden_fields: list[str] = []


class APIKeyUpdateResponse(BaseModel):
    provider_id: str
    api_key_preview: str
    status: str
