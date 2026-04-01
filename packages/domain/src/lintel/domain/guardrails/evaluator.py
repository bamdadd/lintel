"""Simple expression evaluator for guardrail rule conditions (GRD-3).

Phase 1 supports expressions of the form::

    field.path operator value

Operators: ``>``, ``<``, ``>=``, ``<=``, ``==``, ``!=``, ``contains``, ``in``

The special token ``threshold`` on the right-hand side is replaced by the
``threshold`` parameter passed at evaluation time.  The token ``true``/``false``
are coerced to Python booleans.
"""

from __future__ import annotations

import operator
import re
from typing import Any

_OPERATORS: dict[str, Any] = {
    ">": operator.gt,
    "<": operator.lt,
    ">=": operator.ge,
    "<=": operator.le,
    "==": operator.eq,
    "!=": operator.ne,
}

# Pattern: field_path  operator  value
# Captures: (field_path, operator, value)
_EXPR_RE = re.compile(
    r"^(\S+)\s+(>|<|>=|<=|==|!=|contains|in)\s+(.+)$",
)


def _resolve_field(context: dict[str, object], path: str) -> object:
    """Resolve a dotted field path against a context dict.

    Raises ``KeyError`` if any segment is missing.
    """
    current: object = context
    for segment in path.split("."):
        current = current[segment] if isinstance(current, dict) else getattr(current, segment)
    return current


def _coerce_value(raw: str, threshold: float | None) -> object:
    """Coerce a string token to a Python value."""
    stripped = raw.strip().strip("'\"")
    if stripped == "threshold":
        if threshold is None:
            msg = "Rule references 'threshold' but no threshold is configured"
            raise ValueError(msg)
        return threshold
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False
    # Try numeric
    try:
        return int(stripped)
    except ValueError:
        pass
    try:
        return float(stripped)
    except ValueError:
        pass
    return stripped


def evaluate_condition(
    condition: str,
    context: dict[str, Any],
    *,
    threshold: float | None = None,
) -> bool:
    """Evaluate a simple condition expression against a context dict.

    Args:
        condition: Expression string, e.g. ``"rework_rate > threshold"``.
        context: The payload / context dict to evaluate against.
        threshold: Optional threshold value substituted for the ``threshold`` token.

    Returns:
        ``True`` if the condition is met, ``False`` otherwise.

    Raises:
        ValueError: If the expression cannot be parsed or a field is missing.
    """
    condition = condition.strip()
    if not condition:
        msg = "Empty condition expression"
        raise ValueError(msg)

    # Delegate to extended parser for compound expressions (AND/OR/NOT/parens)
    # or operators not supported by the simple regex (starts_with, matches, not_in).
    extended_keywords = {"AND", "OR", "NOT", "starts_with", "matches", "not_in"}
    if any(f" {kw} " in f" {condition} " for kw in extended_keywords) or "(" in condition:
        from lintel.domain.guardrails.condition_lang import evaluate_expression

        return evaluate_expression(condition, context, threshold=threshold)

    match = _EXPR_RE.match(condition)
    if not match:
        msg = f"Cannot parse condition: {condition!r}"
        raise ValueError(msg)

    field_path, op_str, raw_value = match.group(1), match.group(2), match.group(3)

    try:
        lhs = _resolve_field(context, field_path)
    except (KeyError, AttributeError, TypeError) as exc:
        msg = f"Field {field_path!r} not found in context: {exc}"
        raise ValueError(msg) from exc

    rhs = _coerce_value(raw_value, threshold)

    if op_str == "contains":
        if isinstance(lhs, str):
            return str(rhs) in lhs
        if isinstance(lhs, (list, tuple, set, frozenset)):
            return rhs in lhs
        msg = f"'contains' operator requires str or collection, got {type(lhs).__name__}"
        raise ValueError(msg)

    if op_str == "in":
        if isinstance(rhs, str):
            return str(lhs) in rhs
        if isinstance(rhs, (list, tuple, set, frozenset)):
            return lhs in rhs
        msg = f"'in' operator requires str or collection on RHS, got {type(rhs).__name__}"
        raise ValueError(msg)

    op_func = _OPERATORS.get(op_str)
    if op_func is None:
        msg = f"Unknown operator: {op_str!r}"
        raise ValueError(msg)

    try:
        return bool(op_func(lhs, rhs))
    except TypeError as exc:
        msg = f"Cannot compare {type(lhs).__name__} {op_str} {type(rhs).__name__}: {exc}"
        raise ValueError(msg) from exc
