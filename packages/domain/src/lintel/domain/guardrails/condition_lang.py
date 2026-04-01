"""Extended condition language for guardrail rules (GRD-3 Phase 2).

Supports:
- Boolean combinators: ``AND``, ``OR``, ``NOT``
- Nested field access: ``context.step.cost > 1.0``
- String matching: ``contains``, ``starts_with``, ``matches`` (regex)
- List operators: ``in``, ``not_in``
- Parenthesised sub-expressions

Grammar (recursive-descent)::

    expr     := or_expr
    or_expr  := and_expr ("OR" and_expr)*
    and_expr := not_expr ("AND" not_expr)*
    not_expr := "NOT" not_expr | atom
    atom     := "(" expr ")" | comparison
    comparison := field_path op value

The public entry point is :func:`evaluate_expression`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import TYPE_CHECKING

from lintel.domain.guardrails.evaluator import _coerce_value, _resolve_field

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import Any

# ---------------------------------------------------------------------------
# Tokens
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(
    r"""
    \s*(?:
        (?P<LPAREN>\()
      | (?P<RPAREN>\))
      | (?P<OP>>=|<=|!=|==|>|<|contains|starts_with|matches|not_in|in)
      | (?P<BOOL>AND|OR|NOT)
      | (?P<STRING>'[^']*'|"[^"]*")
      | (?P<WORD>[^\s()]+)
    )
    """,
    re.VERBOSE,
)


@dataclass
class _Token:
    kind: str
    value: str
    pos: int


def _tokenize(expression: str) -> list[_Token]:
    tokens: list[_Token] = []
    pos = 0
    while pos < len(expression):
        if expression[pos].isspace():
            pos += 1
            continue
        m = _TOKEN_RE.match(expression, pos)
        if m is None:
            msg = f"Unexpected character at position {pos}: {expression[pos:]!r}"
            raise ValueError(msg)
        for kind in ("LPAREN", "RPAREN", "OP", "BOOL", "STRING", "WORD"):
            val = m.group(kind)
            if val is not None:
                tokens.append(_Token(kind=kind, value=val, pos=pos))
                break
        pos = m.end()
    return tokens


# ---------------------------------------------------------------------------
# AST nodes
# ---------------------------------------------------------------------------


@dataclass
class _Comparison:
    field: str
    op: str
    value: str


@dataclass
class _BoolOp:
    op: str  # "AND" | "OR"
    children: list[ASTNode]


@dataclass
class _NotOp:
    child: ASTNode


ASTNode = _Comparison | _BoolOp | _NotOp

# ---------------------------------------------------------------------------
# Recursive-descent parser
# ---------------------------------------------------------------------------


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    def _peek(self) -> _Token | None:
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _advance(self) -> _Token:
        tok = self._tokens[self._pos]
        self._pos += 1
        return tok

    def _expect(self, kind: str, value: str | None = None) -> _Token:
        tok = self._peek()
        if tok is None:
            msg = f"Unexpected end of expression, expected {kind}"
            raise ValueError(msg)
        if tok.kind != kind or (value is not None and tok.value != value):
            msg = f"Expected {kind}({value}) at pos {tok.pos}, got {tok.kind}({tok.value})"
            raise ValueError(msg)
        return self._advance()

    def parse(self) -> ASTNode:
        node = self._or_expr()
        if self._pos < len(self._tokens):
            tok = self._tokens[self._pos]
            msg = f"Unexpected token at pos {tok.pos}: {tok.value!r}"
            raise ValueError(msg)
        return node

    def _or_expr(self) -> ASTNode:
        left = self._and_expr()
        children: list[ASTNode] = [left]
        while (tok := self._peek()) and tok.kind == "BOOL" and tok.value == "OR":
            self._advance()
            children.append(self._and_expr())
        return _BoolOp("OR", children) if len(children) > 1 else children[0]

    def _and_expr(self) -> ASTNode:
        left = self._not_expr()
        children: list[ASTNode] = [left]
        while (tok := self._peek()) and tok.kind == "BOOL" and tok.value == "AND":
            self._advance()
            children.append(self._not_expr())
        return _BoolOp("AND", children) if len(children) > 1 else children[0]

    def _not_expr(self) -> ASTNode:
        tok = self._peek()
        if tok and tok.kind == "BOOL" and tok.value == "NOT":
            self._advance()
            return _NotOp(self._not_expr())
        return self._atom()

    def _atom(self) -> ASTNode:
        tok = self._peek()
        if tok is None:
            msg = "Unexpected end of expression"
            raise ValueError(msg)
        if tok.kind == "LPAREN":
            self._advance()
            node = self._or_expr()
            self._expect("RPAREN")
            return node
        return self._comparison()

    def _comparison(self) -> _Comparison:
        field_tok = self._expect("WORD")
        op_tok = self._expect("OP")
        val_tok = self._peek()
        if val_tok is None:
            msg = "Expected value after operator"
            raise ValueError(msg)
        if val_tok.kind in ("STRING", "WORD"):
            self._advance()
            return _Comparison(field=field_tok.value, op=op_tok.value, value=val_tok.value)
        msg = f"Expected value at pos {val_tok.pos}, got {val_tok.kind}({val_tok.value})"
        raise ValueError(msg)


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

_CMP_OPS: dict[str, Callable[[object, object], bool]] = {
    ">": lambda a, b: a > b,  # type: ignore[operator]
    "<": lambda a, b: a < b,  # type: ignore[operator]
    ">=": lambda a, b: a >= b,  # type: ignore[operator]
    "<=": lambda a, b: a <= b,  # type: ignore[operator]
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


def _eval_comparison(
    node: _Comparison,
    context: dict[str, object],
    threshold: float | None,
) -> bool:
    try:
        lhs = _resolve_field(context, node.field)
    except (KeyError, AttributeError, TypeError) as exc:
        msg = f"Field {node.field!r} not found in context: {exc}"
        raise ValueError(msg) from exc

    rhs = _coerce_value(node.value, threshold)

    if node.op == "contains":
        if isinstance(lhs, str):
            return str(rhs) in lhs
        if isinstance(lhs, (list, tuple, set, frozenset)):
            return rhs in lhs
        msg = f"'contains' requires str or collection, got {type(lhs).__name__}"
        raise ValueError(msg)

    if node.op == "starts_with":
        if not isinstance(lhs, str):
            msg = f"'starts_with' requires str, got {type(lhs).__name__}"
            raise ValueError(msg)
        return lhs.startswith(str(rhs))

    if node.op == "matches":
        if not isinstance(lhs, str):
            msg = f"'matches' requires str, got {type(lhs).__name__}"
            raise ValueError(msg)
        return bool(re.search(str(rhs), lhs))

    if node.op == "in":
        if isinstance(rhs, (list, tuple, set, frozenset)):
            return lhs in rhs
        if isinstance(rhs, str):
            return str(lhs) in rhs
        msg = f"'in' requires collection or str on RHS, got {type(rhs).__name__}"
        raise ValueError(msg)

    if node.op == "not_in":
        if isinstance(rhs, (list, tuple, set, frozenset)):
            return lhs not in rhs
        if isinstance(rhs, str):
            return str(lhs) not in rhs
        msg = f"'not_in' requires collection or str on RHS, got {type(rhs).__name__}"
        raise ValueError(msg)

    cmp_fn = _CMP_OPS.get(node.op)
    if cmp_fn is None:
        msg = f"Unknown operator: {node.op!r}"
        raise ValueError(msg)
    try:
        return bool(cmp_fn(lhs, rhs))
    except TypeError as exc:
        msg = f"Cannot compare {type(lhs).__name__} {node.op} {type(rhs).__name__}: {exc}"
        raise ValueError(msg) from exc


def _eval_node(
    node: ASTNode,
    context: dict[str, object],
    threshold: float | None,
) -> bool:
    if isinstance(node, _Comparison):
        return _eval_comparison(node, context, threshold)
    if isinstance(node, _BoolOp):
        if node.op == "AND":
            return all(_eval_node(c, context, threshold) for c in node.children)
        # OR
        return any(_eval_node(c, context, threshold) for c in node.children)
    if isinstance(node, _NotOp):
        return not _eval_node(node.child, context, threshold)
    msg = f"Unknown AST node: {type(node)}"  # pragma: no cover
    raise ValueError(msg)  # pragma: no cover


def evaluate_expression(
    expression: str,
    context: dict[str, Any],
    *,
    threshold: float | None = None,
) -> bool:
    """Evaluate a condition expression with boolean combinators.

    Supports ``AND``, ``OR``, ``NOT``, parentheses, nested field access,
    comparison operators (``>``, ``<``, ``>=``, ``<=``, ``==``, ``!=``),
    and string/list operators (``contains``, ``starts_with``, ``matches``,
    ``in``, ``not_in``).

    Args:
        expression: The condition string.
        context: Dict to resolve field paths against.
        threshold: Optional threshold value substituted for ``threshold`` token.

    Returns:
        ``True`` if the expression evaluates to true.

    Raises:
        ValueError: On parse or evaluation errors.
    """
    expression = expression.strip()
    if not expression:
        msg = "Empty condition expression"
        raise ValueError(msg)

    tokens = _tokenize(expression)
    parser = _Parser(tokens)
    ast = parser.parse()
    return _eval_node(ast, context, threshold)
