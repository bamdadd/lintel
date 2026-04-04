"""IncidentHotfixHandler — parse Slack alert, create incident, dispatch hotfix workflow."""

from __future__ import annotations

from datetime import UTC, datetime
import re
from uuid import uuid4

import structlog

from lintel.contracts.types import ThreadRef
from lintel.domain.incidents.types import (
    Alert,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    TimelineEntry,
)
from lintel.workflows.commands import StartWorkflow

logger = structlog.get_logger()

_SEVERITY_MAP: dict[str, IncidentSeverity] = {
    "critical": IncidentSeverity.CRITICAL,
    "crit": IncidentSeverity.CRITICAL,
    "major": IncidentSeverity.MAJOR,
    "high": IncidentSeverity.MAJOR,
    "minor": IncidentSeverity.MINOR,
    "low": IncidentSeverity.MINOR,
    "warning": IncidentSeverity.WARNING,
    "warn": IncidentSeverity.WARNING,
}


def parse_severity(text: str) -> IncidentSeverity:
    """Extract severity from alert text, defaulting to MAJOR."""
    lower = text.lower()
    for keyword, severity in _SEVERITY_MAP.items():
        if keyword in lower:
            return severity
    return IncidentSeverity.MAJOR


def parse_service(text: str) -> str:
    """Extract service name from alert text using common patterns."""
    match = re.search(r"service:(\S+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip(".,;:")
    return ""


class IncidentHotfixHandler:
    """Handles the flow: parse alert → create incident → dispatch hotfix workflow."""

    def from_alert_text(
        self,
        alert_text: str,
        *,
        source: str = "slack",
        project_id: str = "",
        repo_url: str = "",
    ) -> tuple[Incident, StartWorkflow]:
        """Parse alert text and produce an Incident + StartWorkflow command.

        Returns:
            Tuple of (incident, start_workflow_command).
        """
        now = datetime.now(tz=UTC)
        severity = parse_severity(alert_text)
        service = parse_service(alert_text)
        incident_id = uuid4().hex

        alert = Alert(
            alert_id=uuid4().hex,
            source=source,
            message=alert_text,
            severity=severity,
            timestamp=now,
            service=service,
        )

        incident = Incident(
            incident_id=incident_id,
            title=f"Hotfix: {alert_text[:80]}",
            description=alert_text,
            severity=severity,
            status=IncidentStatus.DETECTED,
            detected_at=now,
            source=source,
            affected_services=(service,) if service else (),
            timeline=(
                TimelineEntry(
                    timestamp=now,
                    actor="system",
                    action="detected",
                    details=f"Alert from {source}: {alert.alert_id}",
                ),
            ),
        )

        branch_name = f"hotfix/{incident_id[:12]}"
        thread_ref = ThreadRef(
            workspace_id="incident",
            channel_id="hotfix",
            thread_ts=incident_id,
        )

        command = StartWorkflow(
            thread_ref=thread_ref,
            workflow_type="bug_fix",
            sanitized_messages=(alert_text,),
            project_id=project_id,
            work_item_id=incident_id,
            run_id=uuid4().hex,
            repo_url=repo_url,
            repo_branch=branch_name,
            trigger_context=f"incident:{incident_id}",
        )

        logger.info(
            "incident_hotfix_prepared",
            incident_id=incident_id,
            severity=severity,
            service=service,
        )
        return incident, command
