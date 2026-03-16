"""Unit tests for quality gate evaluator."""

from __future__ import annotations

from lintel.domain.artifacts.gates import QualityGateEvaluator
from lintel.domain.artifacts.models import (
    CoverageReport,
    ParsedArtifact,
    QualityGateRule,
    QualityGateSeverity,
)


def _rule(
    rule_type: str,
    threshold: float,
    severity: QualityGateSeverity = QualityGateSeverity.ERROR,
) -> QualityGateRule:
    return QualityGateRule(
        rule_id="test-rule",
        project_id="proj-1",
        rule_type=rule_type,
        threshold=threshold,
        severity=severity,
    )


def test_min_pass_rate_passes() -> None:
    evaluator = QualityGateEvaluator()
    parsed = ParsedArtifact(total=10, passed=9, failed=1)
    results = evaluator.evaluate(
        rules=[_rule("min_pass_rate", 80.0)],
        parsed=parsed,
    )
    assert len(results) == 1
    assert results[0].passed is True


def test_min_pass_rate_fails() -> None:
    evaluator = QualityGateEvaluator()
    parsed = ParsedArtifact(total=10, passed=5, failed=5)
    results = evaluator.evaluate(
        rules=[_rule("min_pass_rate", 80.0)],
        parsed=parsed,
    )
    assert len(results) == 1
    assert results[0].passed is False
    assert "below threshold" in results[0].message


def test_min_pass_rate_no_tests() -> None:
    evaluator = QualityGateEvaluator()
    results = evaluator.evaluate(
        rules=[_rule("min_pass_rate", 80.0)],
        parsed=None,
    )
    assert len(results) == 1
    assert results[0].passed is False
    assert "No test results" in results[0].message


def test_min_coverage_passes() -> None:
    evaluator = QualityGateEvaluator()
    coverage = CoverageReport(line_rate=0.85)
    results = evaluator.evaluate(
        rules=[_rule("min_coverage", 80.0)],
        coverage=coverage,
    )
    assert len(results) == 1
    assert results[0].passed is True


def test_min_coverage_fails() -> None:
    evaluator = QualityGateEvaluator()
    coverage = CoverageReport(line_rate=0.60)
    results = evaluator.evaluate(
        rules=[_rule("min_coverage", 80.0)],
        coverage=coverage,
    )
    assert len(results) == 1
    assert results[0].passed is False


def test_max_coverage_drop_passes() -> None:
    evaluator = QualityGateEvaluator()
    coverage = CoverageReport(line_rate=0.79)
    previous = CoverageReport(line_rate=0.80)
    results = evaluator.evaluate(
        rules=[_rule("max_coverage_drop", 2.0, QualityGateSeverity.WARN)],
        coverage=coverage,
        previous_coverage=previous,
    )
    assert len(results) == 1
    assert results[0].passed is True


def test_max_coverage_drop_fails() -> None:
    evaluator = QualityGateEvaluator()
    coverage = CoverageReport(line_rate=0.70)
    previous = CoverageReport(line_rate=0.80)
    results = evaluator.evaluate(
        rules=[_rule("max_coverage_drop", 2.0)],
        coverage=coverage,
        previous_coverage=previous,
    )
    assert len(results) == 1
    assert results[0].passed is False
    assert "dropped" in results[0].message


def test_max_coverage_drop_no_previous() -> None:
    evaluator = QualityGateEvaluator()
    coverage = CoverageReport(line_rate=0.70)
    results = evaluator.evaluate(
        rules=[_rule("max_coverage_drop", 2.0)],
        coverage=coverage,
        previous_coverage=None,
    )
    assert len(results) == 1
    assert results[0].passed is True
    assert "No previous coverage" in results[0].message


def test_disabled_rule_skipped() -> None:
    evaluator = QualityGateEvaluator()
    rule = QualityGateRule(
        rule_id="disabled",
        project_id="proj-1",
        rule_type="min_pass_rate",
        threshold=80.0,
        enabled=False,
    )
    results = evaluator.evaluate(rules=[rule], parsed=ParsedArtifact(total=1, failed=1))
    assert len(results) == 0


def test_multiple_rules() -> None:
    evaluator = QualityGateEvaluator()
    parsed = ParsedArtifact(total=10, passed=9, failed=1)
    coverage = CoverageReport(line_rate=0.85)
    rules = [
        _rule("min_pass_rate", 80.0),
        _rule("min_coverage", 80.0),
    ]
    results = evaluator.evaluate(rules=rules, parsed=parsed, coverage=coverage)
    assert len(results) == 2
    assert all(r.passed for r in results)
