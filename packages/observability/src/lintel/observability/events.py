"""Observability domain events."""

from __future__ import annotations

from dataclasses import dataclass

from lintel.contracts.events import EventEnvelope, register_events


@dataclass(frozen=True)
class AuditRecorded(EventEnvelope):
    event_type: str = "AuditRecorded"


@dataclass(frozen=True)
class DeliveryMetricComputed(EventEnvelope):
    event_type: str = "DeliveryMetricComputed"


@dataclass(frozen=True)
class AgentPerformanceComputed(EventEnvelope):
    event_type: str = "AgentPerformanceComputed"


@dataclass(frozen=True)
class HumanPerformanceComputed(EventEnvelope):
    event_type: str = "HumanPerformanceComputed"


register_events(
    AuditRecorded,
    DeliveryMetricComputed,
    AgentPerformanceComputed,
    HumanPerformanceComputed,
)
