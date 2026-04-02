"""Domain types for incident detection and response (REQ-007)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime


class IncidentSeverity(StrEnum):
    """Severity classification for incidents."""

    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    WARNING = "warning"


class IncidentStatus(StrEnum):
    """Lifecycle status of an incident."""

    DETECTED = "detected"
    TRIAGING = "triaging"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    POSTMORTEM = "postmortem"


@dataclass(frozen=True)
class TimelineEntry:
    """A single entry in an incident's timeline."""

    timestamp: datetime
    actor: str
    action: str
    details: str = ""


@dataclass(frozen=True)
class Incident:
    """An incident detected by the system."""

    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus
    detected_at: datetime
    resolved_at: datetime | None = None
    source: str = ""
    affected_services: tuple[str, ...] = ()
    timeline: tuple[TimelineEntry, ...] = ()
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Alert:
    """An incoming alert that may indicate an incident."""

    alert_id: str
    source: str
    message: str
    severity: IncidentSeverity
    timestamp: datetime
    service: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
