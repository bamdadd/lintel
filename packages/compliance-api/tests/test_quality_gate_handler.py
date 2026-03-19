"""Tests for QualityGateGuardrailHandler (REQ-010)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from lintel.compliance_api.quality_gate_handler import QualityGateGuardrailHandler
from lintel.domain.events import CoverageMeasured, TestResultsParsed

if TYPE_CHECKING:
    from lintel.contracts.events import EventEnvelope


class _FakeEventBus:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)


class _FakeRuleStore:
    def __init__(self, rules: list[dict[str, Any]] | None = None) -> None:
        self._rules = rules or []

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [r for r in self._rules if r.get("project_id") == project_id]


class _FakeCoverageStore:
    def __init__(self, latest: dict[str, Any] | None = None) -> None:
        self._latest = latest

    async def get_latest_by_project(self, project_id: str) -> dict[str, Any] | None:
        return self._latest


class TestQualityGateGuardrailHandler:
    async def test_handled_types(self) -> None:
        assert "TestResultsParsed" in QualityGateGuardrailHandler.HANDLED_TYPES
        assert "CoverageMeasured" in QualityGateGuardrailHandler.HANDLED_TYPES

    async def test_skips_when_no_project_id(self) -> None:
        bus = _FakeEventBus()
        handler = QualityGateGuardrailHandler(
            rule_store=_FakeRuleStore(),
            coverage_store=_FakeCoverageStore(),
            event_bus=bus,
        )
        event = TestResultsParsed(payload={"run_id": "r1"})
        await handler.handle(event)
        assert len(bus.published) == 0

    async def test_skips_when_no_rules(self) -> None:
        bus = _FakeEventBus()
        handler = QualityGateGuardrailHandler(
            rule_store=_FakeRuleStore(rules=[]),
            coverage_store=_FakeCoverageStore(),
            event_bus=bus,
        )
        event = TestResultsParsed(
            payload={"run_id": "r1", "project_id": "proj-1", "total": 10, "passed": 10}
        )
        await handler.handle(event)
        assert len(bus.published) == 0

    async def test_evaluates_min_pass_rate_and_publishes(self) -> None:
        bus = _FakeEventBus()
        rules = [
            {
                "rule_id": "qr1",
                "project_id": "proj-1",
                "rule_type": "min_pass_rate",
                "threshold": 90.0,
                "severity": "error",
                "enabled": True,
            }
        ]
        handler = QualityGateGuardrailHandler(
            rule_store=_FakeRuleStore(rules=rules),
            coverage_store=_FakeCoverageStore(),
            event_bus=bus,
        )
        # 80% pass rate should fail the 90% threshold
        event = TestResultsParsed(
            payload={
                "run_id": "r1",
                "project_id": "proj-1",
                "total": 10,
                "passed": 8,
                "failed": 2,
            }
        )
        await handler.handle(event)

        assert len(bus.published) == 1
        gate_event = bus.published[0]
        assert gate_event.event_type == "QualityGateEvaluated"
        assert gate_event.payload["passed"] is False
        assert gate_event.payload["rule_type"] == "min_pass_rate"

    async def test_evaluates_min_coverage_passing(self) -> None:
        bus = _FakeEventBus()
        rules = [
            {
                "rule_id": "qr2",
                "project_id": "proj-1",
                "rule_type": "min_coverage",
                "threshold": 80.0,
                "severity": "warn",
                "enabled": True,
            }
        ]
        handler = QualityGateGuardrailHandler(
            rule_store=_FakeRuleStore(rules=rules),
            coverage_store=_FakeCoverageStore(),
            event_bus=bus,
        )
        event = CoverageMeasured(
            payload={
                "run_id": "r1",
                "project_id": "proj-1",
                "line_rate": 0.85,
                "branch_rate": 0.70,
            }
        )
        await handler.handle(event)

        assert len(bus.published) == 1
        assert bus.published[0].payload["passed"] is True

    async def test_evaluates_coverage_drop(self) -> None:
        bus = _FakeEventBus()
        rules = [
            {
                "rule_id": "qr3",
                "project_id": "proj-1",
                "rule_type": "max_coverage_drop",
                "threshold": 5.0,
                "severity": "error",
                "enabled": True,
            }
        ]
        previous = {"line_rate": 0.90, "branch_rate": 0.80}
        handler = QualityGateGuardrailHandler(
            rule_store=_FakeRuleStore(rules=rules),
            coverage_store=_FakeCoverageStore(latest=previous),
            event_bus=bus,
        )
        # Coverage dropped from 90% to 80% = 10pp drop, exceeds 5pp threshold
        event = CoverageMeasured(
            payload={
                "run_id": "r1",
                "project_id": "proj-1",
                "line_rate": 0.80,
                "branch_rate": 0.70,
            }
        )
        await handler.handle(event)

        assert len(bus.published) == 1
        assert bus.published[0].payload["passed"] is False

    async def test_no_event_bus_does_not_crash(self) -> None:
        rules = [
            {
                "rule_id": "qr1",
                "project_id": "proj-1",
                "rule_type": "min_pass_rate",
                "threshold": 50.0,
                "severity": "error",
                "enabled": True,
            }
        ]
        handler = QualityGateGuardrailHandler(
            rule_store=_FakeRuleStore(rules=rules),
            coverage_store=_FakeCoverageStore(),
            event_bus=None,
        )
        event = TestResultsParsed(
            payload={
                "run_id": "r1",
                "project_id": "proj-1",
                "total": 10,
                "passed": 10,
            }
        )
        # Should not raise
        await handler.handle(event)
