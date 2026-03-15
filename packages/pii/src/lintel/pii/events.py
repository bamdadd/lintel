"""PII domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class PIIDetected(EventEnvelope):
    event_type: str = "PIIDetected"


@dataclass(frozen=True)
class PIIAnonymised(EventEnvelope):
    event_type: str = "PIIAnonymised"


@dataclass(frozen=True)
class PIIResidualRiskBlocked(EventEnvelope):
    event_type: str = "PIIResidualRiskBlocked"


@dataclass(frozen=True)
class VaultRevealRequested(EventEnvelope):
    event_type: str = "VaultRevealRequested"


@dataclass(frozen=True)
class VaultRevealGranted(EventEnvelope):
    event_type: str = "VaultRevealGranted"


register_events(
    PIIDetected,
    PIIAnonymised,
    PIIResidualRiskBlocked,
    VaultRevealRequested,
    VaultRevealGranted,
)
