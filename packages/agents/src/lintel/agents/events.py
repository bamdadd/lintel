"""Agent and skill domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class AgentStepScheduled(EventEnvelope):
    event_type: str = "AgentStepScheduled"


@dataclass(frozen=True)
class AgentStepStarted(EventEnvelope):
    event_type: str = "AgentStepStarted"


@dataclass(frozen=True)
class AgentStepCompleted(EventEnvelope):
    event_type: str = "AgentStepCompleted"


@dataclass(frozen=True)
class AgentDefinitionCreated(EventEnvelope):
    event_type: str = "AgentDefinitionCreated"


@dataclass(frozen=True)
class AgentDefinitionUpdated(EventEnvelope):
    event_type: str = "AgentDefinitionUpdated"


@dataclass(frozen=True)
class AgentDefinitionRemoved(EventEnvelope):
    event_type: str = "AgentDefinitionRemoved"


@dataclass(frozen=True)
class SkillRegistered(EventEnvelope):
    event_type: str = "SkillRegistered"


@dataclass(frozen=True)
class SkillUpdated(EventEnvelope):
    event_type: str = "SkillUpdated"


@dataclass(frozen=True)
class SkillRemoved(EventEnvelope):
    event_type: str = "SkillRemoved"


@dataclass(frozen=True)
class SkillInvoked(EventEnvelope):
    event_type: str = "SkillInvoked"


@dataclass(frozen=True)
class SkillSucceeded(EventEnvelope):
    event_type: str = "SkillSucceeded"


@dataclass(frozen=True)
class SkillFailed(EventEnvelope):
    event_type: str = "SkillFailed"


register_events(
    AgentStepScheduled,
    AgentStepStarted,
    AgentStepCompleted,
    AgentDefinitionCreated,
    AgentDefinitionUpdated,
    AgentDefinitionRemoved,
    SkillRegistered,
    SkillUpdated,
    SkillRemoved,
    SkillInvoked,
    SkillSucceeded,
    SkillFailed,
)
