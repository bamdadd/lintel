"""Quality gate guardrail handler (REQ-010).

Subscribes to TestResultsParsed and CoverageMeasured events,
evaluates quality gate rules, and publishes QualityGateEvaluated
events.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from lintel.artifacts_api.store import CoverageMetricStore, QualityGateRuleStore
    from lintel.contracts.events import EventEnvelope
    from lintel.contracts.protocols import EventBus

logger = structlog.get_logger()


class QualityGateGuardrailHandler:
    """Evaluates quality gate rules when test results or coverage arrive."""

    HANDLED_TYPES: frozenset[str] = frozenset({"TestResultsParsed", "CoverageMeasured"})

    def __init__(
        self,
        rule_store: QualityGateRuleStore,
        coverage_store: CoverageMetricStore,
        event_bus: EventBus | None = None,
    ) -> None:
        self._rule_store = rule_store
        self._coverage_store = coverage_store
        self._event_bus = event_bus

    async def handle(self, event: EventEnvelope) -> None:
        """Handle a test result or coverage event."""
        from lintel.domain.artifacts.gates import (
            QualityGateEvaluator,
        )
        from lintel.domain.artifacts.models import (
            CoverageReport,
            ParsedArtifact,
            QualityGateRule,
            QualityGateSeverity,
        )
        from lintel.domain.events import QualityGateEvaluated

        payload = event.payload
        project_id = payload.get("project_id", "")
        run_id = payload.get("run_id", "")

        if not project_id:
            return

        # Load rules for this project
        raw_rules = await self._rule_store.list_by_project(
            project_id,
        )
        if not raw_rules:
            return

        rules = [
            QualityGateRule(
                rule_id=r.get("rule_id", ""),
                project_id=r.get("project_id", ""),
                rule_type=r.get("rule_type", ""),
                threshold=float(r.get("threshold", 0)),
                severity=QualityGateSeverity(
                    r.get("severity", "error"),
                ),
                enabled=r.get("enabled", True),
            )
            for r in raw_rules
        ]

        # Build domain objects from payload
        parsed: ParsedArtifact | None = None
        coverage: CoverageReport | None = None
        previous_coverage: CoverageReport | None = None

        if event.event_type == "TestResultsParsed":
            parsed = ParsedArtifact(
                total=int(payload.get("total", 0)),
                passed=int(payload.get("passed", 0)),
                failed=int(payload.get("failed", 0)),
                errors=int(payload.get("errors", 0)),
                skipped=int(payload.get("skipped", 0)),
            )
        elif event.event_type == "CoverageMeasured":
            coverage = CoverageReport(
                line_rate=float(payload.get("line_rate", 0.0)),
                branch_rate=float(
                    payload.get("branch_rate", 0.0),
                ),
            )
            # Try to get previous coverage for drop detection
            prev = await self._coverage_store.get_latest_by_project(
                project_id,
            )
            if prev:
                previous_coverage = CoverageReport(
                    line_rate=float(prev.get("line_rate", 0.0)),
                    branch_rate=float(
                        prev.get("branch_rate", 0.0),
                    ),
                )

        evaluator = QualityGateEvaluator()
        results = evaluator.evaluate(
            rules=rules,
            parsed=parsed,
            coverage=coverage,
            previous_coverage=previous_coverage,
        )

        for result in results:
            gate_event = QualityGateEvaluated(
                payload={
                    "run_id": run_id,
                    "project_id": project_id,
                    "rule_id": result.rule_id,
                    "rule_type": result.rule_type,
                    "passed": result.passed,
                    "severity": result.severity.value,
                    "actual_value": result.actual_value,
                    "threshold_value": result.threshold_value,
                    "message": result.message,
                }
            )

            if self._event_bus is not None:
                await self._event_bus.publish(gate_event)

            logger.info(
                "quality_gate_evaluated",
                run_id=run_id,
                project_id=project_id,
                rule_type=result.rule_type,
                passed=result.passed,
                severity=result.severity.value,
            )
