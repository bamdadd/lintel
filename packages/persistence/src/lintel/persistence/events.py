"""Persistence domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class CredentialStored(EventEnvelope):
    event_type: str = "CredentialStored"


@dataclass(frozen=True)
class CredentialRevoked(EventEnvelope):
    event_type: str = "CredentialRevoked"


register_events(
    CredentialStored,
    CredentialRevoked,
)
