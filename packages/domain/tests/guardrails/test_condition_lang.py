"""Tests for the extended condition language (GRD-3 Phase 2)."""

from __future__ import annotations

import pytest

from lintel.domain.guardrails.condition_lang import evaluate_expression
from lintel.domain.guardrails.evaluator import evaluate_condition

# ---------------------------------------------------------------------------
# Basic comparisons (parity with simple evaluator)
# ---------------------------------------------------------------------------


class TestBasicComparisons:
    def test_greater_than(self) -> None:
        assert evaluate_expression("cost > 1.0", {"cost": 2.0}) is True
        assert evaluate_expression("cost > 1.0", {"cost": 0.5}) is False

    def test_less_than(self) -> None:
        assert evaluate_expression("count < 10", {"count": 5}) is True

    def test_equal(self) -> None:
        assert evaluate_expression("status == 'failed'", {"status": "failed"}) is True
        assert evaluate_expression("status == 'failed'", {"status": "ok"}) is False

    def test_not_equal(self) -> None:
        assert evaluate_expression("status != 'ok'", {"status": "failed"}) is True

    def test_gte_lte(self) -> None:
        assert evaluate_expression("x >= 5", {"x": 5}) is True
        assert evaluate_expression("x <= 5", {"x": 5}) is True
        assert evaluate_expression("x >= 5", {"x": 4}) is False

    def test_threshold_substitution(self) -> None:
        assert evaluate_expression("rate > threshold", {"rate": 0.3}, threshold=0.2) is True
        assert evaluate_expression("rate > threshold", {"rate": 0.1}, threshold=0.2) is False

    def test_boolean_coercion(self) -> None:
        assert evaluate_expression("enabled == true", {"enabled": True}) is True
        assert evaluate_expression("enabled == false", {"enabled": False}) is True


# ---------------------------------------------------------------------------
# Nested field access
# ---------------------------------------------------------------------------


class TestNestedFields:
    def test_dotted_path(self) -> None:
        ctx = {"context": {"step": {"cost": 1.5}}}
        assert evaluate_expression("context.step.cost > 1.0", ctx) is True

    def test_missing_field_raises(self) -> None:
        with pytest.raises(ValueError, match="not found"):
            evaluate_expression("a.b.c > 1", {"a": {"b": {}}})


# ---------------------------------------------------------------------------
# String operators
# ---------------------------------------------------------------------------


class TestStringOperators:
    def test_contains(self) -> None:
        assert evaluate_expression("msg contains 'error'", {"msg": "an error occurred"}) is True
        assert evaluate_expression("msg contains 'warn'", {"msg": "an error occurred"}) is False

    def test_starts_with(self) -> None:
        assert evaluate_expression("name starts_with 'pre'", {"name": "prefix"}) is True
        assert evaluate_expression("name starts_with 'suf'", {"name": "prefix"}) is False

    def test_matches_regex(self) -> None:
        assert evaluate_expression(r"code matches '^ERR-\d+'", {"code": "ERR-42"}) is True
        assert evaluate_expression(r"code matches '^ERR-\d+'", {"code": "OK-1"}) is False

    def test_starts_with_non_string_raises(self) -> None:
        with pytest.raises(ValueError, match="starts_with"):
            evaluate_expression("x starts_with 'a'", {"x": 123})

    def test_matches_non_string_raises(self) -> None:
        with pytest.raises(ValueError, match="matches"):
            evaluate_expression("x matches '.*'", {"x": 123})


# ---------------------------------------------------------------------------
# List operators
# ---------------------------------------------------------------------------


class TestListOperators:
    def test_in_string(self) -> None:
        assert evaluate_expression("role in 'admin,editor'", {"role": "admin"}) is True
        assert evaluate_expression("role in 'admin,editor'", {"role": "viewer"}) is False

    def test_not_in_string(self) -> None:
        assert evaluate_expression("role not_in 'admin,editor'", {"role": "viewer"}) is True
        assert evaluate_expression("role not_in 'admin,editor'", {"role": "admin"}) is False

    def test_contains_on_list(self) -> None:
        ctx = {"tags": ["bug", "p0"]}
        assert evaluate_expression("tags contains 'bug'", ctx) is True
        assert evaluate_expression("tags contains 'feature'", ctx) is False


# ---------------------------------------------------------------------------
# Boolean combinators
# ---------------------------------------------------------------------------


class TestBooleanCombinators:
    def test_and(self) -> None:
        ctx = {"cost": 10.0, "status": "failed"}
        assert evaluate_expression("cost > 5 AND status == 'failed'", ctx) is True
        assert evaluate_expression("cost > 5 AND status == 'ok'", ctx) is False

    def test_or(self) -> None:
        ctx = {"cost": 3.0, "retries": 5}
        assert evaluate_expression("cost > 100 OR retries > 3", ctx) is True
        assert evaluate_expression("cost > 100 OR retries > 10", ctx) is False

    def test_not(self) -> None:
        assert evaluate_expression("NOT status == 'ok'", {"status": "failed"}) is True
        assert evaluate_expression("NOT status == 'ok'", {"status": "ok"}) is False

    def test_combined_and_or(self) -> None:
        ctx = {"a": 1, "b": 2, "c": 3}
        # AND binds tighter: a == 1 AND b == 2 OR c == 99 => (True AND True) OR False => True
        assert evaluate_expression("a == 1 AND b == 2 OR c == 99", ctx) is True
        # a == 99 AND b == 2 OR c == 3 => (False AND True) OR True => True
        assert evaluate_expression("a == 99 AND b == 2 OR c == 3", ctx) is True

    def test_parentheses(self) -> None:
        ctx = {"a": 1, "b": 2, "c": 3}
        # a == 1 AND (b == 99 OR c == 3) => True AND True => True
        assert evaluate_expression("a == 1 AND (b == 99 OR c == 3)", ctx) is True
        # (a == 99 OR b == 99) AND c == 3 => False AND True => False
        assert evaluate_expression("(a == 99 OR b == 99) AND c == 3", ctx) is False

    def test_nested_not(self) -> None:
        assert evaluate_expression("NOT NOT x == 1", {"x": 1}) is True

    def test_triple_and(self) -> None:
        ctx = {"a": 1, "b": 2, "c": 3}
        assert evaluate_expression("a == 1 AND b == 2 AND c == 3", ctx) is True
        assert evaluate_expression("a == 1 AND b == 2 AND c == 99", ctx) is False


# ---------------------------------------------------------------------------
# Integration: evaluate_condition delegates to extended parser
# ---------------------------------------------------------------------------


class TestEvaluateConditionDelegation:
    def test_and_via_evaluate_condition(self) -> None:
        ctx = {"cost": 10.0, "status": "failed"}
        assert evaluate_condition("cost > 5 AND status == 'failed'", ctx) is True

    def test_not_via_evaluate_condition(self) -> None:
        assert evaluate_condition("NOT enabled == true", {"enabled": False}) is True

    def test_parens_via_evaluate_condition(self) -> None:
        ctx = {"a": 1, "b": 2}
        assert evaluate_condition("(a == 1 OR b == 99)", ctx) is True

    def test_starts_with_via_evaluate_condition(self) -> None:
        assert evaluate_condition("name starts_with 'pre'", {"name": "prefix"}) is True

    def test_matches_via_evaluate_condition(self) -> None:
        assert evaluate_condition(r"code matches '^ERR'", {"code": "ERR-1"}) is True

    def test_not_in_via_evaluate_condition(self) -> None:
        assert evaluate_condition("role not_in 'admin'", {"role": "viewer"}) is True


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrors:
    def test_empty_expression(self) -> None:
        with pytest.raises(ValueError, match="Empty"):
            evaluate_expression("", {})

    def test_invalid_token(self) -> None:
        with pytest.raises(ValueError, match="Unexpected"):
            evaluate_expression("a > 1 AND", {})

    def test_unclosed_paren(self) -> None:
        with pytest.raises(ValueError, match=r"expected|Unexpected"):
            evaluate_expression("(a > 1", {"a": 2})

    def test_trailing_tokens(self) -> None:
        with pytest.raises(ValueError, match="Unexpected"):
            evaluate_expression("a > 1 b > 2", {"a": 2, "b": 3})
