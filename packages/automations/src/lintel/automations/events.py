"""Automation domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope


@dataclass(frozen=True)
class AutomationCreated(EventEnvelope):
    event_type: str = "AutomationCreated"


@dataclass(frozen=True)
class AutomationUpdated(EventEnvelope):
    event_type: str = "AutomationUpdated"


@dataclass(frozen=True)
class AutomationRemoved(EventEnvelope):
    event_type: str = "AutomationRemoved"


@dataclass(frozen=True)
class AutomationEnabled(EventEnvelope):
    event_type: str = "AutomationEnabled"


@dataclass(frozen=True)
class AutomationDisabled(EventEnvelope):
    event_type: str = "AutomationDisabled"


@dataclass(frozen=True)
class AutomationFired(EventEnvelope):
    event_type: str = "AutomationFired"


@dataclass(frozen=True)
class AutomationSkipped(EventEnvelope):
    event_type: str = "AutomationSkipped"


@dataclass(frozen=True)
class AutomationCancelled(EventEnvelope):
    event_type: str = "AutomationCancelled"
