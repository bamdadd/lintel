"""Model and AI-provider domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class AIProviderCreated(EventEnvelope):
    event_type: str = "AIProviderCreated"


@dataclass(frozen=True)
class AIProviderUpdated(EventEnvelope):
    event_type: str = "AIProviderUpdated"


@dataclass(frozen=True)
class AIProviderRemoved(EventEnvelope):
    event_type: str = "AIProviderRemoved"


@dataclass(frozen=True)
class AIProviderApiKeyUpdated(EventEnvelope):
    event_type: str = "AIProviderApiKeyUpdated"


@dataclass(frozen=True)
class ModelRegistered(EventEnvelope):
    event_type: str = "ModelRegistered"


@dataclass(frozen=True)
class ModelUpdated(EventEnvelope):
    event_type: str = "ModelUpdated"


@dataclass(frozen=True)
class ModelRemoved(EventEnvelope):
    event_type: str = "ModelRemoved"


@dataclass(frozen=True)
class ModelAssignmentCreated(EventEnvelope):
    event_type: str = "ModelAssignmentCreated"


@dataclass(frozen=True)
class ModelAssignmentRemoved(EventEnvelope):
    event_type: str = "ModelAssignmentRemoved"


@dataclass(frozen=True)
class ModelSelected(EventEnvelope):
    event_type: str = "ModelSelected"


@dataclass(frozen=True)
class ModelCallCompleted(EventEnvelope):
    event_type: str = "ModelCallCompleted"


register_events(
    AIProviderCreated,
    AIProviderUpdated,
    AIProviderRemoved,
    AIProviderApiKeyUpdated,
    ModelRegistered,
    ModelUpdated,
    ModelRemoved,
    ModelAssignmentCreated,
    ModelAssignmentRemoved,
    ModelSelected,
    ModelCallCompleted,
)
