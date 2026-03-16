"""Quality gate evaluation engine (REQ-010)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.domain.artifacts.models import (
        CoverageReport,
        ParsedArtifact,
        QualityGateRule,
    )

from lintel.domain.artifacts.models import QualityGateResult


class QualityGateEvaluator:
    """Evaluate quality gate rules against parsed artifacts and coverage."""

    def evaluate(
        self,
        rules: list[QualityGateRule],
        parsed: ParsedArtifact | None = None,
        coverage: CoverageReport | None = None,
        previous_coverage: CoverageReport | None = None,
    ) -> list[QualityGateResult]:
        """Evaluate all enabled rules and return results."""
        results: list[QualityGateResult] = []
        for rule in rules:
            if not rule.enabled:
                continue
            result = self._evaluate_rule(rule, parsed, coverage, previous_coverage)
            if result is not None:
                results.append(result)
        return results

    def _evaluate_rule(
        self,
        rule: QualityGateRule,
        parsed: ParsedArtifact | None,
        coverage: CoverageReport | None,
        previous_coverage: CoverageReport | None,
    ) -> QualityGateResult | None:
        handler = _RULE_HANDLERS.get(rule.rule_type)
        if handler is None:
            return None
        return handler(rule, parsed, coverage, previous_coverage)


def _eval_min_pass_rate(
    rule: QualityGateRule,
    parsed: ParsedArtifact | None,
    coverage: CoverageReport | None,
    previous_coverage: CoverageReport | None,
) -> QualityGateResult:
    if parsed is None or parsed.total == 0:
        return QualityGateResult(
            rule_id=rule.rule_id,
            rule_type=rule.rule_type,
            passed=False,
            severity=rule.severity,
            actual_value=0.0,
            threshold_value=rule.threshold,
            message="No test results available",
        )
    actual = parsed.pass_rate
    passed = actual >= rule.threshold
    return QualityGateResult(
        rule_id=rule.rule_id,
        rule_type=rule.rule_type,
        passed=passed,
        severity=rule.severity,
        actual_value=round(actual, 2),
        threshold_value=rule.threshold,
        message="" if passed else (f"Pass rate {actual:.1f}% is below threshold {rule.threshold}%"),
    )


def _eval_min_coverage(
    rule: QualityGateRule,
    parsed: ParsedArtifact | None,
    coverage: CoverageReport | None,
    previous_coverage: CoverageReport | None,
) -> QualityGateResult:
    if coverage is None:
        return QualityGateResult(
            rule_id=rule.rule_id,
            rule_type=rule.rule_type,
            passed=False,
            severity=rule.severity,
            actual_value=0.0,
            threshold_value=rule.threshold,
            message="No coverage data available",
        )
    actual = coverage.line_rate * 100.0
    passed = actual >= rule.threshold
    return QualityGateResult(
        rule_id=rule.rule_id,
        rule_type=rule.rule_type,
        passed=passed,
        severity=rule.severity,
        actual_value=round(actual, 2),
        threshold_value=rule.threshold,
        message="" if passed else (f"Coverage {actual:.1f}% is below threshold {rule.threshold}%"),
    )


def _eval_max_coverage_drop(
    rule: QualityGateRule,
    parsed: ParsedArtifact | None,
    coverage: CoverageReport | None,
    previous_coverage: CoverageReport | None,
) -> QualityGateResult:
    if coverage is None or previous_coverage is None:
        return QualityGateResult(
            rule_id=rule.rule_id,
            rule_type=rule.rule_type,
            passed=True,
            severity=rule.severity,
            actual_value=0.0,
            threshold_value=rule.threshold,
            message="No previous coverage to compare",
        )
    current = coverage.line_rate * 100.0
    previous = previous_coverage.line_rate * 100.0
    drop = previous - current
    passed = drop <= rule.threshold
    return QualityGateResult(
        rule_id=rule.rule_id,
        rule_type=rule.rule_type,
        passed=passed,
        severity=rule.severity,
        actual_value=round(drop, 2),
        threshold_value=rule.threshold,
        message="" if passed else (f"Coverage dropped {drop:.1f}pp (threshold {rule.threshold}pp)"),
    )


_RULE_HANDLERS = {
    "min_pass_rate": _eval_min_pass_rate,
    "min_coverage": _eval_min_coverage,
    "max_coverage_drop": _eval_max_coverage_drop,
}
