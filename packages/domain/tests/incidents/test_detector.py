"""Tests for IncidentDetector."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.incidents.detector import IncidentDetector
from lintel.domain.incidents.types import (
    Alert,
    IncidentSeverity,
    IncidentStatus,
    TimelineEntry,
)


def _make_alert(
    *,
    severity: IncidentSeverity = IncidentSeverity.MAJOR,
    service: str = "api",
    alert_id: str = "a1",
) -> Alert:
    return Alert(
        alert_id=alert_id,
        source="test",
        message="something broke",
        severity=severity,
        timestamp=datetime.now(tz=UTC),
        service=service,
    )


def test_detect_creates_incident() -> None:
    detector = IncidentDetector()
    alert = _make_alert()
    incident = detector.detect(alert)
    assert incident is not None
    assert incident.status == IncidentStatus.DETECTED
    assert incident.severity == IncidentSeverity.MAJOR
    assert len(incident.timeline) == 1
    assert incident.affected_services == ("api",)


def test_detect_below_threshold_returns_none() -> None:
    detector = IncidentDetector(severity_threshold=IncidentSeverity.MAJOR)
    alert = _make_alert(severity=IncidentSeverity.MINOR)
    assert detector.detect(alert) is None


def test_correlate_alerts_groups_by_service() -> None:
    detector = IncidentDetector()
    alerts = [
        _make_alert(alert_id="a1", service="api"),
        _make_alert(alert_id="a2", service="api"),
        _make_alert(alert_id="a3", service="db"),
    ]
    incidents = detector.correlate_alerts(alerts)
    assert len(incidents) == 2
    services = {inc.affected_services[0] for inc in incidents}
    assert services == {"api", "db"}


def test_correlate_alerts_ungrouped() -> None:
    detector = IncidentDetector()
    alerts = [_make_alert(service="")]
    incidents = detector.correlate_alerts(alerts)
    assert len(incidents) == 1


def test_escalate_increases_severity() -> None:
    detector = IncidentDetector()
    alert = _make_alert(severity=IncidentSeverity.MINOR)
    incident = detector.detect(alert)
    assert incident is not None

    escalated = detector.escalate(incident)
    assert escalated.severity == IncidentSeverity.MAJOR
    assert len(escalated.timeline) == 2
    assert escalated.timeline[-1].action == "escalated"


def test_escalate_critical_stays_critical() -> None:
    detector = IncidentDetector()
    alert = _make_alert(severity=IncidentSeverity.CRITICAL)
    incident = detector.detect(alert)
    assert incident is not None

    escalated = detector.escalate(incident)
    assert escalated.severity == IncidentSeverity.CRITICAL


def test_add_timeline() -> None:
    detector = IncidentDetector()
    alert = _make_alert()
    incident = detector.detect(alert)
    assert incident is not None

    entry = TimelineEntry(
        timestamp=datetime.now(tz=UTC),
        actor="alice",
        action="acknowledged",
        details="On it",
    )
    updated = detector.add_timeline(incident.incident_id, entry)
    assert len(updated.timeline) == 2
    assert updated.timeline[-1].actor == "alice"


def test_add_timeline_unknown_raises() -> None:
    detector = IncidentDetector()
    entry = TimelineEntry(
        timestamp=datetime.now(tz=UTC),
        actor="bob",
        action="test",
    )
    try:
        detector.add_timeline("nonexistent", entry)
        msg = "Expected KeyError"
        raise AssertionError(msg)
    except KeyError:
        pass


def test_get_incident() -> None:
    detector = IncidentDetector()
    alert = _make_alert()
    incident = detector.detect(alert)
    assert incident is not None

    retrieved = detector.get(incident.incident_id)
    assert retrieved is not None
    assert retrieved.incident_id == incident.incident_id
    assert detector.get("nonexistent") is None
