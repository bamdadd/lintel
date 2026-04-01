"""Unit tests for the guardrail condition evaluator."""

from __future__ import annotations

import pytest

from lintel.domain.guardrails.evaluator import evaluate_condition

# ---------------------------------------------------------------------------
# Comparison operators with threshold
# ---------------------------------------------------------------------------


class TestThresholdComparisons:
    def test_greater_than_true(self) -> None:
        assert evaluate_condition("rework_rate > threshold", {"rework_rate": 0.3}, threshold=0.2)

    def test_greater_than_false(self) -> None:
        assert not evaluate_condition(
            "rework_rate > threshold", {"rework_rate": 0.1}, threshold=0.2
        )

    def test_less_than(self) -> None:
        assert evaluate_condition("score < threshold", {"score": 10}, threshold=50.0)

    def test_greater_equal(self) -> None:
        assert evaluate_condition("count >= threshold", {"count": 3}, threshold=3.0)

    def test_less_equal(self) -> None:
        assert evaluate_condition("count <= threshold", {"count": 2}, threshold=3.0)

    def test_threshold_not_configured_raises(self) -> None:
        with pytest.raises(ValueError, match="no threshold is configured"):
            evaluate_condition("x > threshold", {"x": 1})


# ---------------------------------------------------------------------------
# Equality operators
# ---------------------------------------------------------------------------


class TestEqualityOperators:
    def test_equal_string(self) -> None:
        assert evaluate_condition("verdict == 'failed'", {"verdict": "failed"})

    def test_equal_string_false(self) -> None:
        assert not evaluate_condition("verdict == 'failed'", {"verdict": "passed"})

    def test_not_equal(self) -> None:
        assert evaluate_condition("status != 'ok'", {"status": "error"})

    def test_equal_boolean_true(self) -> None:
        assert evaluate_condition("pii_detected == true", {"pii_detected": True})

    def test_equal_boolean_false(self) -> None:
        assert not evaluate_condition("pii_detected == true", {"pii_detected": False})

    def test_equal_numeric(self) -> None:
        assert evaluate_condition("count == 5", {"count": 5})


# ---------------------------------------------------------------------------
# Nested field paths
# ---------------------------------------------------------------------------


class TestNestedFields:
    def test_dotted_path(self) -> None:
        ctx = {"payload": {"token_usage": {"total_tokens": 150000}}}
        assert evaluate_condition(
            "payload.token_usage.total_tokens > threshold", ctx, threshold=100000.0
        )

    def test_missing_field_raises(self) -> None:
        with pytest.raises(ValueError, match="not found in context"):
            evaluate_condition("missing.field > 1", {"other": 1})


# ---------------------------------------------------------------------------
# Contains / in operators
# ---------------------------------------------------------------------------


class TestContainsOperator:
    def test_string_contains(self) -> None:
        assert evaluate_condition("message contains error", {"message": "an error occurred"})

    def test_string_contains_false(self) -> None:
        assert not evaluate_condition("message contains error", {"message": "all good"})

    def test_list_contains(self) -> None:
        assert evaluate_condition("tags contains critical", {"tags": ["critical", "bug"]})


class TestInOperator:
    def test_in_string(self) -> None:
        assert evaluate_condition("char in abcdef", {"char": "c"})

    def test_in_string_false(self) -> None:
        assert not evaluate_condition("char in abcdef", {"char": "z"})


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_condition_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty condition"):
            evaluate_condition("", {"x": 1})

    def test_unparseable_condition_raises(self) -> None:
        with pytest.raises(ValueError, match="Cannot parse"):
            evaluate_condition("not a valid expr", {"x": 1})

    def test_whitespace_stripped(self) -> None:
        assert evaluate_condition("  x > threshold  ", {"x": 10}, threshold=5.0)
