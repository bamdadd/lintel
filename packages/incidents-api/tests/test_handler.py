"""Tests for IncidentHotfixHandler."""

from lintel.domain.incidents.types import IncidentSeverity, IncidentStatus
from lintel.incidents_api.handler import (
    IncidentHotfixHandler,
    parse_service,
    parse_severity,
)


class TestParseSeverity:
    def test_critical(self) -> None:
        assert parse_severity("CRITICAL: server down") == IncidentSeverity.CRITICAL

    def test_crit_alias(self) -> None:
        assert parse_severity("crit error in prod") == IncidentSeverity.CRITICAL

    def test_major(self) -> None:
        assert parse_severity("HIGH latency detected") == IncidentSeverity.MAJOR

    def test_minor(self) -> None:
        assert parse_severity("low priority issue") == IncidentSeverity.MINOR

    def test_warning(self) -> None:
        assert parse_severity("warn: disk space") == IncidentSeverity.WARNING

    def test_default_major(self) -> None:
        assert parse_severity("something broke") == IncidentSeverity.MAJOR


class TestParseService:
    def test_service_colon(self) -> None:
        assert parse_service("service:payments is down") == "payments"

    def test_service_space(self) -> None:
        assert parse_service("service:api-gateway failing") == "api-gateway"

    def test_no_service(self) -> None:
        assert parse_service("alert without service info") == ""


class TestIncidentHotfixHandler:
    def test_from_alert_text_creates_incident(self) -> None:
        handler = IncidentHotfixHandler()
        incident, _command = handler.from_alert_text(
            "CRITICAL: service:payments is down",
            project_id="proj-1",
            repo_url="https://github.com/org/repo",
        )
        assert incident.severity == IncidentSeverity.CRITICAL
        assert incident.status == IncidentStatus.DETECTED
        assert "payments" in incident.affected_services
        assert incident.source == "slack"
        assert len(incident.timeline) == 1

    def test_from_alert_text_creates_workflow_command(self) -> None:
        handler = IncidentHotfixHandler()
        incident, command = handler.from_alert_text(
            "CRITICAL: service:payments is down",
            project_id="proj-1",
            repo_url="https://github.com/org/repo",
        )
        assert command.workflow_type == "bug_fix"
        assert command.project_id == "proj-1"
        assert command.repo_url == "https://github.com/org/repo"
        assert command.repo_branch.startswith("hotfix/")
        assert command.trigger_context.startswith("incident:")
        assert command.work_item_id == incident.incident_id

    def test_from_alert_text_custom_source(self) -> None:
        handler = IncidentHotfixHandler()
        incident, _ = handler.from_alert_text("alert", source="pagerduty", project_id="p")
        assert incident.source == "pagerduty"
