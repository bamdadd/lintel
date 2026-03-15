"""Sandbox domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class SandboxJobScheduled(EventEnvelope):
    event_type: str = "SandboxJobScheduled"


@dataclass(frozen=True)
class SandboxCreated(EventEnvelope):
    event_type: str = "SandboxCreated"


@dataclass(frozen=True)
class SandboxCommandExecuted(EventEnvelope):
    event_type: str = "SandboxCommandExecuted"


@dataclass(frozen=True)
class SandboxFileWritten(EventEnvelope):
    event_type: str = "SandboxFileWritten"


@dataclass(frozen=True)
class SandboxArtifactsCollected(EventEnvelope):
    event_type: str = "SandboxArtifactsCollected"


@dataclass(frozen=True)
class SandboxDestroyed(EventEnvelope):
    event_type: str = "SandboxDestroyed"


register_events(
    SandboxJobScheduled,
    SandboxCreated,
    SandboxCommandExecuted,
    SandboxFileWritten,
    SandboxArtifactsCollected,
    SandboxDestroyed,
)
