"""Post-test quality gate evaluation.

After tests complete in a pipeline, evaluate configured quality gate rules
(min pass rate, min coverage, max coverage drop) and report results.
Gates with severity=error cause the pipeline to fail; severity=warn logs warnings.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from lintel.workflows.nodes._stage_tracking import StageTracker


class _QualityGateRuleStore(Protocol):
    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]: ...


class _CoverageMetricStore(Protocol):
    async def get_latest_by_project(self, project_id: str) -> dict[str, Any] | None: ...


logger = structlog.get_logger()


async def evaluate_quality_gates(
    *,
    project_id: str,
    run_id: str,
    test_passed: bool,
    test_total: int,
    test_failures: int,
    coverage_line_rate: float | None,
    tracker: StageTracker,
    quality_gate_rule_store: _QualityGateRuleStore | None,
    coverage_metric_store: _CoverageMetricStore | None = None,
) -> list[dict[str, Any]]:
    """Evaluate quality gates after test execution.

    Loads rules from the quality_gate_rule_store for the project,
    builds ParsedArtifact and CoverageReport from test results,
    and runs the QualityGateEvaluator.

    Returns list of gate results. Logs warnings/errors to the stage tracker.
    """
    from lintel.domain.artifacts.gates import QualityGateEvaluator
    from lintel.domain.artifacts.models import (
        CoverageReport,
        ParsedArtifact,
        QualityGateRule,
        QualityGateSeverity,
    )

    if quality_gate_rule_store is None:
        return []

    # Load rules for the project
    try:
        raw_rules = await quality_gate_rule_store.list_by_project(project_id)
    except Exception:
        logger.warning("quality_gate_load_rules_failed", project_id=project_id)
        return []

    if not raw_rules:
        return []

    # Convert dict rules to QualityGateRule dataclasses
    rules: list[QualityGateRule] = []
    for r in raw_rules:
        if isinstance(r, dict):
            rules.append(
                QualityGateRule(
                    rule_id=r["rule_id"],
                    project_id=r["project_id"],
                    rule_type=r["rule_type"],
                    threshold=float(r["threshold"]),
                    severity=QualityGateSeverity(r.get("severity", "error")),
                    enabled=r.get("enabled", True),
                )
            )
        else:
            rules.append(r)

    # Build ParsedArtifact from test stats
    test_passed_count = test_total - test_failures if test_total > 0 else 0
    parsed = ParsedArtifact(
        total=test_total,
        passed=test_passed_count,
        failed=test_failures,
    )

    # Build CoverageReport if we have coverage data
    coverage: CoverageReport | None = None
    if coverage_line_rate is not None:
        coverage = CoverageReport(line_rate=coverage_line_rate)

    # Get previous coverage for drop calculation
    previous_coverage: CoverageReport | None = None
    if coverage_metric_store is not None:
        try:
            prev = await coverage_metric_store.get_latest_by_project(project_id)
            if prev is not None:
                previous_coverage = CoverageReport(
                    line_rate=float(prev.get("line_rate", 0.0)),
                )
        except Exception:
            logger.warning("quality_gate_previous_coverage_failed")

    # Evaluate
    evaluator = QualityGateEvaluator()
    results = evaluator.evaluate(
        rules=rules,
        parsed=parsed,
        coverage=coverage,
        previous_coverage=previous_coverage,
    )

    # Log results
    gate_failures: list[dict[str, Any]] = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        severity = result.severity.value.upper()
        line = f"Quality gate [{severity}] {result.rule_type}: {status}"
        if result.message:
            line += f" — {result.message}"
        await tracker.append_log("test", line)

        result_dict = {
            "rule_id": result.rule_id,
            "rule_type": result.rule_type,
            "passed": result.passed,
            "severity": result.severity.value,
            "actual_value": result.actual_value,
            "threshold_value": result.threshold_value,
            "message": result.message,
        }
        if not result.passed:
            gate_failures.append(result_dict)

    if gate_failures:
        error_gates = [g for g in gate_failures if g["severity"] == "error"]
        warn_gates = [g for g in gate_failures if g["severity"] == "warn"]
        if error_gates:
            await tracker.append_log(
                "test",
                f"Quality gates: {len(error_gates)} error(s), {len(warn_gates)} warning(s)",
            )
        elif warn_gates:
            await tracker.append_log(
                "test",
                f"Quality gates: {len(warn_gates)} warning(s) (non-blocking)",
            )

    logger.info(
        "quality_gates_evaluated",
        project_id=project_id,
        run_id=run_id,
        total_rules=len(rules),
        failures=len(gate_failures),
    )

    return [
        {
            "rule_id": r.rule_id,
            "rule_type": r.rule_type,
            "passed": r.passed,
            "severity": r.severity.value,
            "actual_value": r.actual_value,
            "threshold_value": r.threshold_value,
            "message": r.message,
        }
        for r in results
    ]


def has_blocking_failures(gate_results: list[dict[str, Any]]) -> bool:
    """Check if any quality gate results have severity=error and failed."""
    return any(not r["passed"] and r["severity"] == "error" for r in gate_results)
