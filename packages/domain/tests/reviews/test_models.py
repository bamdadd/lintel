"""Tests for review domain models (REQ-F006)."""

from __future__ import annotations

import pytest

from lintel.domain.reviews.models import (
    CodebaseReview,
    FileReview,
    Finding,
    FindingSeverity,
    ReviewDimension,
    ReviewPolicy,
)


def _make_finding(
    dim: ReviewDimension = ReviewDimension.CORRECTNESS,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
) -> Finding:
    return Finding(dimension=dim, severity=severity, message="test finding")


def _make_file_review(
    path: str = "main.py",
    overall: float = 7.0,
    findings: tuple[Finding, ...] = (),
) -> FileReview:
    scores = {d: overall for d in ReviewDimension}
    return FileReview(
        file_path=path,
        dimension_scores=scores,
        findings=findings,
        overall_score=overall,
    )


class TestReviewDimension:
    def test_all_five_dimensions(self) -> None:
        assert len(ReviewDimension) == 5
        assert ReviewDimension.CORRECTNESS == "correctness"
        assert ReviewDimension.SECURITY == "security"
        assert ReviewDimension.PERFORMANCE == "performance"
        assert ReviewDimension.MAINTAINABILITY == "maintainability"
        assert ReviewDimension.ARCHITECTURE == "architecture"


class TestFinding:
    def test_frozen(self) -> None:
        f = _make_finding()
        with pytest.raises(AttributeError):
            f.message = "changed"  # type: ignore[misc]

    def test_optional_fields(self) -> None:
        f = Finding(
            dimension=ReviewDimension.SECURITY,
            severity=FindingSeverity.HIGH,
            message="sql injection",
            line=42,
            suggestion="use parameterised queries",
        )
        assert f.line == 42
        assert f.suggestion == "use parameterised queries"


class TestFileReview:
    def test_has_critical_true(self) -> None:
        fr = _make_file_review(findings=(_make_finding(severity=FindingSeverity.CRITICAL),))
        assert fr.has_critical is True

    def test_has_critical_false(self) -> None:
        fr = _make_file_review(findings=(_make_finding(severity=FindingSeverity.LOW),))
        assert fr.has_critical is False

    def test_findings_by_dimension(self) -> None:
        findings = (
            _make_finding(dim=ReviewDimension.SECURITY),
            _make_finding(dim=ReviewDimension.SECURITY),
            _make_finding(dim=ReviewDimension.PERFORMANCE),
        )
        fr = _make_file_review(findings=findings)
        grouped = fr.findings_by_dimension
        assert len(grouped[ReviewDimension.SECURITY]) == 2
        assert len(grouped[ReviewDimension.PERFORMANCE]) == 1


class TestCodebaseReview:
    def test_files_below_threshold(self) -> None:
        reviews = (
            _make_file_review("a.py", overall=3.0),
            _make_file_review("b.py", overall=8.0),
        )
        cr = CodebaseReview(
            review_id="r1",
            file_reviews=reviews,
            summary_scores={d: 5.5 for d in ReviewDimension},
            overall_score=5.5,
        )
        below = cr.files_below_threshold
        assert len(below) == 1
        assert below[0].file_path == "a.py"

    def test_total_findings(self) -> None:
        reviews = (
            _make_file_review(findings=(_make_finding(), _make_finding())),
            _make_file_review(findings=(_make_finding(),)),
        )
        cr = CodebaseReview(
            review_id="r2",
            file_reviews=reviews,
            summary_scores={},
            overall_score=7.0,
        )
        assert cr.total_findings == 3

    def test_critical_files(self) -> None:
        reviews = (
            _make_file_review(
                "bad.py",
                findings=(_make_finding(severity=FindingSeverity.CRITICAL),),
            ),
            _make_file_review("good.py"),
        )
        cr = CodebaseReview(
            review_id="r3",
            file_reviews=reviews,
            summary_scores={},
            overall_score=6.0,
        )
        assert len(cr.critical_files) == 1


class TestReviewPolicy:
    def test_defaults(self) -> None:
        p = ReviewPolicy()
        assert p.min_score_threshold == 5.0
        assert p.fail_on_critical is True
        assert len(p.dimensions) == 5

    def test_effective_weights_default(self) -> None:
        p = ReviewPolicy()
        weights = p.effective_weights()
        assert len(weights) == 5
        assert pytest.approx(sum(weights.values()), abs=1e-9) == 1.0

    def test_effective_weights_custom(self) -> None:
        p = ReviewPolicy(weights={ReviewDimension.SECURITY: 0.5})
        weights = p.effective_weights()
        assert weights[ReviewDimension.SECURITY] == 0.5

    def test_should_auto_fix(self) -> None:
        p = ReviewPolicy(auto_fix_min_severity=FindingSeverity.MEDIUM)
        assert p.should_auto_fix(FindingSeverity.HIGH) is True
        assert p.should_auto_fix(FindingSeverity.MEDIUM) is True
        assert p.should_auto_fix(FindingSeverity.LOW) is False
        assert p.should_auto_fix(FindingSeverity.INFO) is False
