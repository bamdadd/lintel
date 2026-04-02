"""Observability platform integration domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
import uuid


class ObservabilityProvider(StrEnum):
    """Supported observability platforms."""

    DATADOG = "datadog"
    GRAFANA = "grafana"
    NEWRELIC = "newrelic"
    GENERIC_OTEL = "generic_otel"


class AlertSeverity(StrEnum):
    """Alert severity levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass(frozen=True)
class Alert:
    """Normalized alert from an observability provider."""

    alert_id: str
    provider: ObservabilityProvider
    external_id: str
    title: str
    description: str
    severity: AlertSeverity
    status: str
    source_service: str = ""
    triggered_at: datetime | None = None
    resolved_at: datetime | None = None
    url: str = ""


@dataclass(frozen=True)
class MetricExport:
    """A single metric data point for export to an observability platform."""

    metric_name: str
    value: float
    tags: dict[str, str] = field(default_factory=dict)
    timestamp: datetime | None = None
    provider: ObservabilityProvider = ObservabilityProvider.GENERIC_OTEL


class ObservabilityBridge:
    """Bridge between Lintel and external observability platforms.

    Ingests alerts from providers, exports metrics, and manages alert lifecycle.
    """

    def __init__(self) -> None:
        self._alerts: dict[str, Alert] = {}

    def ingest_alert(
        self,
        payload: dict[str, Any],
        provider: ObservabilityProvider,
    ) -> Alert:
        """Parse a raw alert payload from an observability provider into an Alert."""
        alert_id = str(uuid.uuid4())
        alert = Alert(
            alert_id=alert_id,
            provider=provider,
            external_id=str(payload.get("external_id", "")),
            title=str(payload.get("title", "")),
            description=str(payload.get("description", "")),
            severity=AlertSeverity(payload.get("severity", "info")),
            status=str(payload.get("status", "open")),
            source_service=str(payload.get("source_service", "")),
            triggered_at=payload.get("triggered_at"),
            resolved_at=payload.get("resolved_at"),
            url=str(payload.get("url", "")),
        )
        self._alerts[alert_id] = alert
        return alert

    def export_metric(self, metric: MetricExport) -> bool:
        """Export a metric to the configured observability provider.

        Returns True if the metric was accepted for export.
        In a real implementation this would forward to the provider's API.
        """
        return bool(metric.metric_name)

    def list_alerts(
        self,
        *,
        provider: ObservabilityProvider | None = None,
        severity: AlertSeverity | None = None,
        status: str | None = None,
    ) -> list[Alert]:
        """List alerts with optional filters."""
        results = list(self._alerts.values())
        if provider is not None:
            results = [a for a in results if a.provider == provider]
        if severity is not None:
            results = [a for a in results if a.severity == severity]
        if status is not None:
            results = [a for a in results if a.status == status]
        return results

    def acknowledge_alert(self, alert_id: str) -> Alert | None:
        """Acknowledge an alert by ID, returning the updated alert or None."""
        existing = self._alerts.get(alert_id)
        if existing is None:
            return None
        updated = Alert(
            alert_id=existing.alert_id,
            provider=existing.provider,
            external_id=existing.external_id,
            title=existing.title,
            description=existing.description,
            severity=existing.severity,
            status="acknowledged",
            source_service=existing.source_service,
            triggered_at=existing.triggered_at,
            resolved_at=existing.resolved_at,
            url=existing.url,
        )
        self._alerts[alert_id] = updated
        return updated

    def get_alert(self, alert_id: str) -> Alert | None:
        """Get a single alert by ID."""
        return self._alerts.get(alert_id)

    def resolve_alert(self, alert_id: str) -> Alert | None:
        """Mark an alert as resolved."""
        existing = self._alerts.get(alert_id)
        if existing is None:
            return None
        now = datetime.now(tz=UTC)
        updated = Alert(
            alert_id=existing.alert_id,
            provider=existing.provider,
            external_id=existing.external_id,
            title=existing.title,
            description=existing.description,
            severity=existing.severity,
            status="resolved",
            source_service=existing.source_service,
            triggered_at=existing.triggered_at,
            resolved_at=now,
            url=existing.url,
        )
        self._alerts[alert_id] = updated
        return updated
