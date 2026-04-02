"""Tests for observability integration domain model."""

from __future__ import annotations

from datetime import UTC, datetime

from lintel.domain.integrations.observability import (
    Alert,
    AlertSeverity,
    MetricExport,
    ObservabilityBridge,
    ObservabilityProvider,
)


class TestObservabilityProvider:
    def test_enum_values(self) -> None:
        assert ObservabilityProvider.DATADOG == "datadog"
        assert ObservabilityProvider.GRAFANA == "grafana"
        assert ObservabilityProvider.NEWRELIC == "newrelic"
        assert ObservabilityProvider.GENERIC_OTEL == "generic_otel"


class TestAlertSeverity:
    def test_enum_values(self) -> None:
        assert AlertSeverity.CRITICAL == "critical"
        assert AlertSeverity.HIGH == "high"
        assert AlertSeverity.MEDIUM == "medium"
        assert AlertSeverity.LOW == "low"
        assert AlertSeverity.INFO == "info"


class TestAlert:
    def test_frozen(self) -> None:
        alert = Alert(
            alert_id="a1",
            provider=ObservabilityProvider.DATADOG,
            external_id="ext-1",
            title="CPU spike",
            description="CPU > 90%",
            severity=AlertSeverity.HIGH,
            status="open",
        )
        assert alert.alert_id == "a1"
        assert alert.provider == ObservabilityProvider.DATADOG
        assert alert.source_service == ""
        assert alert.url == ""

    def test_with_optional_fields(self) -> None:
        now = datetime.now(tz=UTC)
        alert = Alert(
            alert_id="a2",
            provider=ObservabilityProvider.GRAFANA,
            external_id="ext-2",
            title="Latency",
            description="p99 > 500ms",
            severity=AlertSeverity.MEDIUM,
            status="open",
            source_service="api-gateway",
            triggered_at=now,
            url="https://grafana.example.com/alert/1",
        )
        assert alert.triggered_at == now
        assert alert.source_service == "api-gateway"


class TestMetricExport:
    def test_defaults(self) -> None:
        metric = MetricExport(metric_name="cpu.usage", value=85.5)
        assert metric.tags == {}
        assert metric.timestamp is None
        assert metric.provider == ObservabilityProvider.GENERIC_OTEL

    def test_with_tags(self) -> None:
        metric = MetricExport(
            metric_name="request.count",
            value=42.0,
            tags={"env": "prod", "service": "api"},
            provider=ObservabilityProvider.DATADOG,
        )
        assert metric.tags["env"] == "prod"
        assert metric.provider == ObservabilityProvider.DATADOG


class TestObservabilityBridge:
    def test_ingest_alert(self) -> None:
        bridge = ObservabilityBridge()
        alert = bridge.ingest_alert(
            {
                "external_id": "dd-123",
                "title": "High error rate",
                "description": "Error rate > 5%",
                "severity": "critical",
                "status": "open",
                "source_service": "payments",
            },
            ObservabilityProvider.DATADOG,
        )
        assert alert.provider == ObservabilityProvider.DATADOG
        assert alert.severity == AlertSeverity.CRITICAL
        assert alert.title == "High error rate"
        assert alert.source_service == "payments"

    def test_ingest_alert_defaults(self) -> None:
        bridge = ObservabilityBridge()
        alert = bridge.ingest_alert({}, ObservabilityProvider.GENERIC_OTEL)
        assert alert.severity == AlertSeverity.INFO
        assert alert.status == "open"
        assert alert.title == ""

    def test_export_metric_success(self) -> None:
        bridge = ObservabilityBridge()
        metric = MetricExport(metric_name="cpu.usage", value=85.5)
        assert bridge.export_metric(metric) is True

    def test_export_metric_empty_name(self) -> None:
        bridge = ObservabilityBridge()
        metric = MetricExport(metric_name="", value=0.0)
        assert bridge.export_metric(metric) is False

    def test_list_alerts_no_filter(self) -> None:
        bridge = ObservabilityBridge()
        bridge.ingest_alert({"title": "A1", "severity": "high"}, ObservabilityProvider.DATADOG)
        bridge.ingest_alert({"title": "A2", "severity": "low"}, ObservabilityProvider.GRAFANA)
        assert len(bridge.list_alerts()) == 2

    def test_list_alerts_filter_provider(self) -> None:
        bridge = ObservabilityBridge()
        bridge.ingest_alert({"title": "A1"}, ObservabilityProvider.DATADOG)
        bridge.ingest_alert({"title": "A2"}, ObservabilityProvider.GRAFANA)
        results = bridge.list_alerts(provider=ObservabilityProvider.DATADOG)
        assert len(results) == 1
        assert results[0].title == "A1"

    def test_list_alerts_filter_severity(self) -> None:
        bridge = ObservabilityBridge()
        bridge.ingest_alert({"title": "A1", "severity": "critical"}, ObservabilityProvider.DATADOG)
        bridge.ingest_alert({"title": "A2", "severity": "low"}, ObservabilityProvider.DATADOG)
        results = bridge.list_alerts(severity=AlertSeverity.CRITICAL)
        assert len(results) == 1
        assert results[0].severity == AlertSeverity.CRITICAL

    def test_list_alerts_filter_status(self) -> None:
        bridge = ObservabilityBridge()
        alert = bridge.ingest_alert({"title": "A1"}, ObservabilityProvider.DATADOG)
        bridge.acknowledge_alert(alert.alert_id)
        results = bridge.list_alerts(status="acknowledged")
        assert len(results) == 1

    def test_acknowledge_alert(self) -> None:
        bridge = ObservabilityBridge()
        alert = bridge.ingest_alert(
            {"title": "Test", "severity": "high"}, ObservabilityProvider.NEWRELIC
        )
        updated = bridge.acknowledge_alert(alert.alert_id)
        assert updated is not None
        assert updated.status == "acknowledged"
        assert updated.title == "Test"

    def test_acknowledge_nonexistent(self) -> None:
        bridge = ObservabilityBridge()
        assert bridge.acknowledge_alert("nonexistent") is None

    def test_get_alert(self) -> None:
        bridge = ObservabilityBridge()
        alert = bridge.ingest_alert({"title": "X"}, ObservabilityProvider.DATADOG)
        fetched = bridge.get_alert(alert.alert_id)
        assert fetched is not None
        assert fetched.title == "X"

    def test_get_alert_nonexistent(self) -> None:
        bridge = ObservabilityBridge()
        assert bridge.get_alert("missing") is None

    def test_resolve_alert(self) -> None:
        bridge = ObservabilityBridge()
        alert = bridge.ingest_alert({"title": "R"}, ObservabilityProvider.GRAFANA)
        resolved = bridge.resolve_alert(alert.alert_id)
        assert resolved is not None
        assert resolved.status == "resolved"
        assert resolved.resolved_at is not None

    def test_resolve_nonexistent(self) -> None:
        bridge = ObservabilityBridge()
        assert bridge.resolve_alert("nope") is None
