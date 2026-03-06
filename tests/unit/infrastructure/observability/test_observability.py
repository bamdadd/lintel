"""Tests for observability: correlation, logging, tracing."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from lintel.infrastructure.observability.correlation import (
    correlation_id_var,
    get_correlation_id,
    set_correlation_id,
)
from lintel.infrastructure.observability.logging import configure_logging
from lintel.infrastructure.observability.tracing import configure_tracing


class TestCorrelationId:
    def test_get_returns_uuid(self) -> None:
        cid = get_correlation_id()
        assert isinstance(cid, UUID)

    def test_set_and_get(self) -> None:
        new_id = uuid4()
        set_correlation_id(new_id)
        assert get_correlation_id() == new_id

    def test_token_reset(self) -> None:
        original = get_correlation_id()
        new_id = uuid4()
        token = set_correlation_id(new_id)
        assert get_correlation_id() == new_id
        correlation_id_var.reset(token)
        assert get_correlation_id() == original

    async def test_async_isolation(self) -> None:
        """Correlation IDs should be isolated across async tasks."""
        id_a = uuid4()
        id_b = uuid4()
        results: dict[str, UUID] = {}

        async def task_a() -> None:
            set_correlation_id(id_a)
            await asyncio.sleep(0.01)
            results["a"] = get_correlation_id()

        async def task_b() -> None:
            set_correlation_id(id_b)
            await asyncio.sleep(0.01)
            results["b"] = get_correlation_id()

        await asyncio.gather(task_a(), task_b())
        assert results["a"] == id_a
        assert results["b"] == id_b


class TestConfigureLogging:
    def test_json_format(self) -> None:
        configure_logging(log_level="DEBUG", log_format="json")

    def test_console_format(self) -> None:
        configure_logging(log_level="INFO", log_format="console")


class TestConfigureTracing:
    def test_noop_without_endpoint(self) -> None:
        tracer = configure_tracing(otel_endpoint="")
        assert tracer is not None

    def test_with_endpoint(self) -> None:
        tracer = configure_tracing(otel_endpoint="http://localhost:4317")
        assert tracer is not None
