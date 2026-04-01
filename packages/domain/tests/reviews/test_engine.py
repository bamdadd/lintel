"""Tests for ReviewEngine (REQ-F006)."""

from __future__ import annotations

from unittest.mock import patch

from lintel.domain.reviews.engine import ReviewEngine
from lintel.domain.reviews.models import (
    Finding,
    FindingSeverity,
    ReviewDimension,
    ReviewPolicy,
)


def _finding(
    dim: ReviewDimension = ReviewDimension.CORRECTNESS,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
    msg: str = "issue",
) -> Finding:
    return Finding(dimension=dim, severity=severity, message=msg)


def _scores(value: float = 7.0) -> dict[ReviewDimension, float]:
    return {d: value for d in ReviewDimension}


class TestReviewFile:
    def test_basic_review(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        fr = engine.review_file("app.py", _scores(8.0), [])
        assert fr.file_path == "app.py"
        assert fr.overall_score == 8.0
        assert len(fr.findings) == 0

    def test_clamps_scores(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        scores = {ReviewDimension.CORRECTNESS: 15.0, ReviewDimension.SECURITY: -3.0}
        fr = engine.review_file("x.py", scores, [])
        assert fr.dimension_scores[ReviewDimension.CORRECTNESS] == 10.0
        assert fr.dimension_scores[ReviewDimension.SECURITY] == 0.0

    def test_fills_missing_dimensions(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        fr = engine.review_file("x.py", {ReviewDimension.CORRECTNESS: 8.0}, [])
        assert ReviewDimension.PERFORMANCE in fr.dimension_scores
        assert fr.dimension_scores[ReviewDimension.PERFORMANCE] == 0.0

    def test_truncates_findings(self) -> None:
        policy = ReviewPolicy(max_findings_per_file=2)
        engine = ReviewEngine(policy)
        findings = [_finding(msg=f"f{i}") for i in range(5)]
        fr = engine.review_file("x.py", _scores(), findings)
        assert len(fr.findings) == 2


class TestAggregate:
    def test_empty(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        cr = engine.aggregate([])
        assert cr.overall_score == 0.0
        assert len(cr.file_reviews) == 0

    def test_averages_scores(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        fr1 = engine.review_file("a.py", _scores(6.0), [])
        fr2 = engine.review_file("b.py", _scores(8.0), [])
        cr = engine.aggregate([fr1, fr2])
        assert cr.overall_score == 7.0
        assert cr.summary_scores[ReviewDimension.CORRECTNESS] == 7.0

    def test_review_id_unique(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        cr1 = engine.aggregate([])
        cr2 = engine.aggregate([])
        assert cr1.review_id != cr2.review_id


class TestPassesPolicy:
    def test_passes_above_threshold(self) -> None:
        engine = ReviewEngine(ReviewPolicy(min_score_threshold=5.0))
        fr = engine.review_file("a.py", _scores(8.0), [])
        cr = engine.aggregate([fr])
        assert engine.passes_policy(cr) is True

    def test_fails_below_threshold(self) -> None:
        engine = ReviewEngine(ReviewPolicy(min_score_threshold=8.0))
        fr = engine.review_file("a.py", _scores(5.0), [])
        cr = engine.aggregate([fr])
        assert engine.passes_policy(cr) is False

    def test_fails_on_critical(self) -> None:
        engine = ReviewEngine(ReviewPolicy(fail_on_critical=True))
        findings = [_finding(severity=FindingSeverity.CRITICAL)]
        fr = engine.review_file("a.py", _scores(9.0), findings)
        cr = engine.aggregate([fr])
        assert engine.passes_policy(cr) is False

    def test_passes_critical_when_disabled(self) -> None:
        engine = ReviewEngine(ReviewPolicy(fail_on_critical=False))
        findings = [_finding(severity=FindingSeverity.CRITICAL)]
        fr = engine.review_file("a.py", _scores(9.0), findings)
        cr = engine.aggregate([fr])
        assert engine.passes_policy(cr) is True


class TestFindingsToFix:
    def test_filters_by_severity(self) -> None:
        engine = ReviewEngine(ReviewPolicy(auto_fix_min_severity=FindingSeverity.HIGH))
        findings = [
            _finding(severity=FindingSeverity.LOW),
            _finding(severity=FindingSeverity.HIGH),
            _finding(severity=FindingSeverity.CRITICAL),
        ]
        fr = engine.review_file("a.py", _scores(), findings)
        cr = engine.aggregate([fr])
        fixable = engine.findings_to_fix(cr)
        assert len(fixable) == 2


class TestGenerateReport:
    def test_report_structure(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        fr = engine.review_file("a.py", _scores(7.0), [_finding()])
        cr = engine.aggregate([fr])
        report = engine.generate_report(cr)
        assert report["review_id"] == cr.review_id
        assert report["overall_score"] == cr.overall_score
        assert report["total_findings"] == 1
        assert report["file_count"] == 1
        assert report["passes_policy"] is True
        assert isinstance(report["summary_scores"], dict)

    def test_report_with_deterministic_id(self) -> None:
        engine = ReviewEngine(ReviewPolicy())
        with patch("lintel.domain.reviews.engine.uuid.uuid4") as mock_uuid:
            mock_uuid.return_value.hex = "abc123"
            cr = engine.aggregate([])
        report = engine.generate_report(cr)
        assert report["review_id"] == "abc123"
