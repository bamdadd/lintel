"""Integration tests for QualityGateGuardrailHandler."""

from __future__ import annotations

from lintel.artifacts_api.store import CoverageMetricStore, QualityGateRuleStore
from lintel.compliance_api.quality_gate_handler import QualityGateGuardrailHandler
from lintel.contracts.events import EventEnvelope


class MockEventBus:
    def __init__(self) -> None:
        self.published: list[EventEnvelope] = []

    async def publish(self, event: EventEnvelope) -> None:
        self.published.append(event)

    async def subscribe(self, event_types: list[str], handler: object) -> str:
        return "mock"

    async def unsubscribe(self, sub_id: str) -> None:
        pass


async def test_handles_test_results_parsed_with_passing_rule() -> None:
    rule_store = QualityGateRuleStore()
    await rule_store.add(
        {
            "rule_id": "r1",
            "project_id": "proj1",
            "rule_type": "min_pass_rate",
            "threshold": 80,
            "severity": "error",
            "enabled": True,
        }
    )
    coverage_store = CoverageMetricStore()
    bus = MockEventBus()
    handler = QualityGateGuardrailHandler(rule_store, coverage_store, bus)

    event = EventEnvelope(
        event_type="TestResultsParsed",
        payload={
            "project_id": "proj1",
            "run_id": "run1",
            "total": 10,
            "passed": 9,
            "failed": 1,
        },
    )
    await handler.handle(event)

    assert len(bus.published) == 1
    assert bus.published[0].payload["passed"] is True


async def test_handles_test_results_parsed_with_failing_rule() -> None:
    rule_store = QualityGateRuleStore()
    await rule_store.add(
        {
            "rule_id": "r1",
            "project_id": "proj1",
            "rule_type": "min_pass_rate",
            "threshold": 80,
            "severity": "error",
            "enabled": True,
        }
    )
    coverage_store = CoverageMetricStore()
    bus = MockEventBus()
    handler = QualityGateGuardrailHandler(rule_store, coverage_store, bus)

    event = EventEnvelope(
        event_type="TestResultsParsed",
        payload={
            "project_id": "proj1",
            "run_id": "run1",
            "total": 10,
            "passed": 7,
            "failed": 3,
        },
    )
    await handler.handle(event)

    assert len(bus.published) == 1
    assert bus.published[0].payload["passed"] is False


async def test_handles_coverage_measured() -> None:
    rule_store = QualityGateRuleStore()
    await rule_store.add(
        {
            "rule_id": "r1",
            "project_id": "proj1",
            "rule_type": "min_coverage",
            "threshold": 70,
            "severity": "error",
            "enabled": True,
        }
    )
    coverage_store = CoverageMetricStore()
    bus = MockEventBus()
    handler = QualityGateGuardrailHandler(rule_store, coverage_store, bus)

    event = EventEnvelope(
        event_type="CoverageMeasured",
        payload={
            "project_id": "proj1",
            "run_id": "run1",
            "line_rate": 0.8,
            "branch_rate": 0.6,
        },
    )
    await handler.handle(event)

    assert len(bus.published) == 1
    assert bus.published[0].payload["passed"] is True


async def test_handles_coverage_drop_with_previous() -> None:
    rule_store = QualityGateRuleStore()
    await rule_store.add(
        {
            "rule_id": "r1",
            "project_id": "proj1",
            "rule_type": "max_coverage_drop",
            "threshold": 5,
            "severity": "error",
            "enabled": True,
        }
    )
    coverage_store = CoverageMetricStore()
    await coverage_store.save(
        metric_id="m0",
        run_id="run0",
        project_id="proj1",
        artifact_id="a0",
        data={"line_rate": 0.8, "branch_rate": 0.7},
    )
    bus = MockEventBus()
    handler = QualityGateGuardrailHandler(rule_store, coverage_store, bus)

    event = EventEnvelope(
        event_type="CoverageMeasured",
        payload={
            "project_id": "proj1",
            "run_id": "run1",
            "line_rate": 0.7,
            "branch_rate": 0.6,
        },
    )
    await handler.handle(event)

    assert len(bus.published) == 1
    assert bus.published[0].payload["passed"] is False


async def test_no_rules_no_events() -> None:
    rule_store = QualityGateRuleStore()
    coverage_store = CoverageMetricStore()
    bus = MockEventBus()
    handler = QualityGateGuardrailHandler(rule_store, coverage_store, bus)

    event = EventEnvelope(
        event_type="TestResultsParsed",
        payload={
            "project_id": "proj1",
            "run_id": "run1",
            "total": 10,
            "passed": 9,
            "failed": 1,
        },
    )
    await handler.handle(event)

    assert len(bus.published) == 0


async def test_no_project_id_skips() -> None:
    rule_store = QualityGateRuleStore()
    await rule_store.add(
        {
            "rule_id": "r1",
            "project_id": "proj1",
            "rule_type": "min_pass_rate",
            "threshold": 80,
            "severity": "error",
            "enabled": True,
        }
    )
    coverage_store = CoverageMetricStore()
    bus = MockEventBus()
    handler = QualityGateGuardrailHandler(rule_store, coverage_store, bus)

    event = EventEnvelope(
        event_type="TestResultsParsed",
        payload={
            "run_id": "run1",
            "total": 10,
            "passed": 9,
            "failed": 1,
        },
    )
    await handler.handle(event)

    assert len(bus.published) == 0
