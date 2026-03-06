"""Prometheus-compatible metrics via OpenTelemetry."""

from __future__ import annotations

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider


def configure_metrics() -> metrics.Meter:
    """Configure OpenTelemetry metrics and return a Meter for lintel."""
    provider = MeterProvider()
    metrics.set_meter_provider(provider)
    return metrics.get_meter("lintel")
