"""Model and AI-provider domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AIProviderType(StrEnum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    AZURE_OPENAI = "azure_openai"
    GOOGLE = "google"
    OLLAMA = "ollama"
    BEDROCK = "bedrock"
    CLAUDE_CODE = "claude_code"
    CUSTOM = "custom"


@dataclass(frozen=True)
class AIProvider:
    """A configured AI model provider with API credentials."""

    provider_id: str
    provider_type: AIProviderType
    name: str
    api_base: str = ""
    is_default: bool = False
    models: tuple[str, ...] = ()
    config: dict[str, object] | None = None


class TokenStatus(StrEnum):
    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"
    NOT_CONFIGURED = "not_configured"


@dataclass(frozen=True)
class ModelPolicy:
    """Policy for model selection per agent role."""

    provider: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0
    extra_params: dict[str, object] | None = None


@dataclass(frozen=True)
class Model:
    """A specific AI model available through a provider."""

    model_id: str
    provider_id: str
    name: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0
    is_default: bool = False
    capabilities: tuple[str, ...] = ()
    config: dict[str, object] | None = None


class ModelAssignmentContext(StrEnum):
    """Where a model can be used."""

    TASK = "task"
    CHAT = "chat"
    WORKFLOW_STEP = "workflow_step"
    PIPELINE_STEP = "pipeline_step"
    AGENT_ROLE = "agent_role"


@dataclass(frozen=True)
class ModelAssignment:
    """Binds a model to a usage context."""

    assignment_id: str
    model_id: str
    context: ModelAssignmentContext
    context_id: str
    priority: int = 0
