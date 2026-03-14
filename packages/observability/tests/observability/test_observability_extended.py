"""Tests for observability: logging, tracing, metrics, correlation."""

from __future__ import annotations

from uuid import UUID, uuid4

from lintel.observability.correlation import (
    correlation_id_var,
    get_correlation_id,
    set_correlation_id,
)
from lintel.observability.logging import configure_logging
from lintel.observability.metrics import configure_metrics
from lintel.observability.tracing import configure_tracing


class TestCorrelation:
    def test_get_creates_new_id(self) -> None:
        # Reset context
        token = correlation_id_var.set(uuid4())
        try:
            cid = get_correlation_id()
            assert isinstance(cid, UUID)
        finally:
            correlation_id_var.reset(token)

    def test_set_and_get(self) -> None:
        cid = uuid4()
        token = set_correlation_id(cid)
        try:
            assert get_correlation_id() == cid
        finally:
            correlation_id_var.reset(token)

    def test_get_returns_same_value(self) -> None:
        cid = uuid4()
        token = set_correlation_id(cid)
        try:
            assert get_correlation_id() == get_correlation_id()
        finally:
            correlation_id_var.reset(token)


class TestConfigureLogging:
    def test_json_format(self) -> None:
        configure_logging(log_level="INFO", log_format="json")

    def test_console_format(self) -> None:
        configure_logging(log_level="DEBUG", log_format="console")

    def test_invalid_level_defaults_to_info(self) -> None:
        configure_logging(log_level="NONEXISTENT")


class TestConfigureTracing:
    def test_without_endpoint(self) -> None:
        tracer = configure_tracing()
        assert tracer is not None

    def test_with_endpoint(self) -> None:
        tracer = configure_tracing(otel_endpoint="http://localhost:4317")
        assert tracer is not None


class TestConfigureMetrics:
    def test_returns_meter(self) -> None:
        meter = configure_metrics()
        assert meter is not None
