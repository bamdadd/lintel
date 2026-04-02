"""Tests for incident domain types."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.incidents.types import (
    Alert,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    TimelineEntry,
)


def test_incident_severity_values() -> None:
    assert IncidentSeverity.CRITICAL == "critical"
    assert IncidentSeverity.MAJOR == "major"
    assert IncidentSeverity.MINOR == "minor"
    assert IncidentSeverity.WARNING == "warning"


def test_incident_status_values() -> None:
    assert IncidentStatus.DETECTED == "detected"
    assert IncidentStatus.TRIAGING == "triaging"
    assert IncidentStatus.MITIGATING == "mitigating"
    assert IncidentStatus.RESOLVED == "resolved"
    assert IncidentStatus.POSTMORTEM == "postmortem"


def test_timeline_entry_creation() -> None:
    now = datetime.now(tz=UTC)
    entry = TimelineEntry(timestamp=now, actor="alice", action="acknowledged")
    assert entry.timestamp == now
    assert entry.actor == "alice"
    assert entry.details == ""


def test_incident_defaults() -> None:
    now = datetime.now(tz=UTC)
    incident = Incident(
        incident_id="inc-1",
        title="Test",
        description="desc",
        severity=IncidentSeverity.MINOR,
        status=IncidentStatus.DETECTED,
        detected_at=now,
    )
    assert incident.resolved_at is None
    assert incident.source == ""
    assert incident.affected_services == ()
    assert incident.timeline == ()
    assert incident.tags == ()


def test_alert_creation() -> None:
    now = datetime.now(tz=UTC)
    alert = Alert(
        alert_id="a1",
        source="prometheus",
        message="CPU high",
        severity=IncidentSeverity.MAJOR,
        timestamp=now,
        service="api-server",
    )
    assert alert.service == "api-server"
    assert alert.metadata == {}
