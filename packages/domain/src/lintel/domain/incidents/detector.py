"""Incident detection and correlation engine (REQ-007)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
import uuid

from lintel.domain.incidents.types import (
    Alert,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    TimelineEntry,
)


@dataclass
class IncidentDetector:
    """Detects, correlates, and manages incidents from incoming alerts."""

    _incidents: dict[str, Incident] = field(default_factory=dict)
    severity_threshold: IncidentSeverity = IncidentSeverity.WARNING

    def detect(self, alert: Alert) -> Incident | None:
        """Evaluate an alert and create an incident if it meets the threshold.

        Returns the created Incident, or None if the alert is below threshold.
        """
        severity_order = list(IncidentSeverity)
        if severity_order.index(alert.severity) > severity_order.index(self.severity_threshold):
            return None

        now = datetime.now(tz=UTC)
        incident = Incident(
            incident_id=uuid.uuid4().hex,
            title=f"Incident from {alert.source}: {alert.message[:80]}",
            description=alert.message,
            severity=alert.severity,
            status=IncidentStatus.DETECTED,
            detected_at=now,
            source=alert.source,
            affected_services=(alert.service,) if alert.service else (),
            timeline=(
                TimelineEntry(
                    timestamp=now,
                    actor="system",
                    action="detected",
                    details=f"Alert {alert.alert_id} from {alert.source}",
                ),
            ),
        )
        self._incidents[incident.incident_id] = incident
        return incident

    def correlate_alerts(self, alerts: list[Alert]) -> list[Incident]:
        """Group related alerts by service and create one incident per group.

        Alerts sharing the same service are correlated into a single incident.
        Alerts without a service each become their own incident.
        """
        by_service: dict[str, list[Alert]] = defaultdict(list)
        ungrouped: list[Alert] = []

        for alert in alerts:
            if alert.service:
                by_service[alert.service].append(alert)
            else:
                ungrouped.append(alert)

        incidents: list[Incident] = []
        now = datetime.now(tz=UTC)

        for service, group in by_service.items():
            worst = min(group, key=lambda a: list(IncidentSeverity).index(a.severity))
            timeline = tuple(
                TimelineEntry(
                    timestamp=a.timestamp,
                    actor="system",
                    action="alert_correlated",
                    details=a.message,
                )
                for a in group
            )
            incident = Incident(
                incident_id=uuid.uuid4().hex,
                title=f"Correlated incident for {service} ({len(group)} alerts)",
                description=f"Multiple alerts detected for {service}",
                severity=worst.severity,
                status=IncidentStatus.DETECTED,
                detected_at=now,
                source=group[0].source,
                affected_services=(service,),
                timeline=timeline,
            )
            self._incidents[incident.incident_id] = incident
            incidents.append(incident)

        for alert in ungrouped:
            result = self.detect(alert)
            if result is not None:
                incidents.append(result)

        return incidents

    def escalate(self, incident: Incident) -> Incident:
        """Escalate an incident's severity by one level (if possible).

        Returns a new Incident with the escalated severity and a timeline entry.
        """
        severity_order = list(IncidentSeverity)
        current_idx = severity_order.index(incident.severity)
        new_severity = severity_order[max(0, current_idx - 1)]

        now = datetime.now(tz=UTC)
        escalated = Incident(
            incident_id=incident.incident_id,
            title=incident.title,
            description=incident.description,
            severity=new_severity,
            status=incident.status,
            detected_at=incident.detected_at,
            resolved_at=incident.resolved_at,
            source=incident.source,
            affected_services=incident.affected_services,
            timeline=(
                *incident.timeline,
                TimelineEntry(
                    timestamp=now,
                    actor="system",
                    action="escalated",
                    details=f"Severity changed from {incident.severity} to {new_severity}",
                ),
            ),
            tags=incident.tags,
        )
        self._incidents[escalated.incident_id] = escalated
        return escalated

    def add_timeline(self, incident_id: str, entry: TimelineEntry) -> Incident:
        """Append a timeline entry to an existing incident.

        Raises KeyError if the incident_id is not found.
        """
        incident = self._incidents[incident_id]
        updated = Incident(
            incident_id=incident.incident_id,
            title=incident.title,
            description=incident.description,
            severity=incident.severity,
            status=incident.status,
            detected_at=incident.detected_at,
            resolved_at=incident.resolved_at,
            source=incident.source,
            affected_services=incident.affected_services,
            timeline=(*incident.timeline, entry),
            tags=incident.tags,
        )
        self._incidents[incident_id] = updated
        return updated

    def get(self, incident_id: str) -> Incident | None:
        """Retrieve an incident by ID."""
        return self._incidents.get(incident_id)
