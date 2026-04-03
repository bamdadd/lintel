"""Tests for PRReviewFormatter."""

from __future__ import annotations

from lintel.domain.reviews.formatter import PRReviewFormatter
from lintel.domain.reviews.models import (
    CodebaseReview,
    FileReview,
    Finding,
    FindingSeverity,
    ReviewDimension,
    ReviewPolicy,
)


def _scores(value: float = 7.0) -> dict[ReviewDimension, float]:
    return {d: value for d in ReviewDimension}


def _finding(
    dim: ReviewDimension = ReviewDimension.CORRECTNESS,
    severity: FindingSeverity = FindingSeverity.MEDIUM,
    msg: str = "issue found",
    line: int | None = 10,
    suggestion: str = "",
) -> Finding:
    return Finding(dimension=dim, severity=severity, message=msg, line=line, suggestion=suggestion)


def _make_review(
    file_reviews: tuple[FileReview, ...],
    overall: float = 7.0,
) -> CodebaseReview:
    summary = _scores(overall)
    return CodebaseReview(
        review_id="test-review-id",
        file_reviews=file_reviews,
        summary_scores=summary,
        overall_score=overall,
    )


class TestFormatReviewEvent:
    def test_passing_review_is_comment(self) -> None:
        fr = FileReview(
            file_path="app.py",
            dimension_scores=_scores(8.0),
            findings=(),
            overall_score=8.0,
        )
        review = _make_review((fr,), overall=8.0)
        policy = ReviewPolicy(min_score_threshold=5.0)
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert result["event"] == "COMMENT"

    def test_failing_review_is_request_changes(self) -> None:
        fr = FileReview(
            file_path="app.py",
            dimension_scores=_scores(3.0),
            findings=(),
            overall_score=3.0,
        )
        review = _make_review((fr,), overall=3.0)
        policy = ReviewPolicy(min_score_threshold=5.0)
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert result["event"] == "REQUEST_CHANGES"

    def test_critical_finding_fails_policy(self) -> None:
        finding = _finding(severity=FindingSeverity.CRITICAL, line=5)
        fr = FileReview(
            file_path="app.py",
            dimension_scores=_scores(9.0),
            findings=(finding,),
            overall_score=9.0,
        )
        review = _make_review((fr,), overall=9.0)
        policy = ReviewPolicy(fail_on_critical=True)
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert result["event"] == "REQUEST_CHANGES"


class TestFormatReviewBody:
    def test_body_contains_overall_score(self) -> None:
        review = _make_review((), overall=7.5)
        policy = ReviewPolicy()
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert "7.5" in result["body"]

    def test_body_contains_verdict(self) -> None:
        review = _make_review((), overall=8.0)
        policy = ReviewPolicy(min_score_threshold=5.0)
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert "PASS" in result["body"]

    def test_body_contains_dimension_scores(self) -> None:
        review = _make_review((), overall=7.0)
        policy = ReviewPolicy()
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert "Correctness" in result["body"]
        assert "Security" in result["body"]

    def test_orphan_findings_in_body(self) -> None:
        finding = _finding(line=None, msg="orphan issue")
        fr = FileReview(
            file_path="lib.py",
            dimension_scores=_scores(),
            findings=(finding,),
            overall_score=7.0,
        )
        review = _make_review((fr,), overall=7.0)
        policy = ReviewPolicy()
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert "orphan issue" in result["body"]
        assert "lib.py" in result["body"]


class TestInlineComments:
    def test_findings_with_line_become_comments(self) -> None:
        f1 = _finding(line=10, msg="fix this")
        f2 = _finding(line=20, msg="and this")
        fr = FileReview(
            file_path="main.py",
            dimension_scores=_scores(),
            findings=(f1, f2),
            overall_score=7.0,
        )
        review = _make_review((fr,))
        policy = ReviewPolicy()
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert len(result["comments"]) == 2
        assert result["comments"][0]["path"] == "main.py"
        assert result["comments"][0]["line"] == 10
        assert "fix this" in result["comments"][0]["body"]

    def test_findings_without_line_excluded_from_comments(self) -> None:
        f1 = _finding(line=None, msg="no line")
        fr = FileReview(
            file_path="main.py",
            dimension_scores=_scores(),
            findings=(f1,),
            overall_score=7.0,
        )
        review = _make_review((fr,))
        policy = ReviewPolicy()
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert len(result["comments"]) == 0

    def test_finding_with_suggestion_in_comment_body(self) -> None:
        f1 = _finding(line=5, msg="bad pattern", suggestion="use X instead")
        fr = FileReview(
            file_path="main.py",
            dimension_scores=_scores(),
            findings=(f1,),
            overall_score=7.0,
        )
        review = _make_review((fr,))
        policy = ReviewPolicy()
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        assert "use X instead" in result["comments"][0]["body"]

    def test_multiple_files(self) -> None:
        f1 = _finding(line=1, msg="issue a")
        f2 = _finding(line=2, msg="issue b")
        fr1 = FileReview(
            file_path="a.py",
            dimension_scores=_scores(),
            findings=(f1,),
            overall_score=7.0,
        )
        fr2 = FileReview(
            file_path="b.py",
            dimension_scores=_scores(),
            findings=(f2,),
            overall_score=7.0,
        )
        review = _make_review((fr1, fr2))
        policy = ReviewPolicy()
        formatter = PRReviewFormatter()
        result = formatter.format_review(review, policy)
        paths = [c["path"] for c in result["comments"]]
        assert "a.py" in paths
        assert "b.py" in paths
