"""Domain models for guardrail rules."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class GuardrailAction(StrEnum):
    WARN = "WARN"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


class RuleVerdict(StrEnum):
    """Outcome of evaluating a single guardrail rule."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"
    ERROR = "ERROR"


@dataclass(frozen=True)
class GuardrailRule:
    """A configurable guardrail rule that evaluates events and triggers actions."""

    rule_id: str
    name: str
    event_type: str
    condition: str
    action: GuardrailAction
    threshold: float | None = None
    cooldown_seconds: int = 0
    is_default: bool = True
    enabled: bool = True


@dataclass(frozen=True)
class RuleEvaluation:
    """Result of evaluating a single rule against a context."""

    rule: GuardrailRule
    verdict: RuleVerdict
    triggered: bool
    message: str = ""


@dataclass(frozen=True)
class EvaluationResult:
    """Aggregate result of evaluating multiple rules."""

    evaluations: tuple[RuleEvaluation, ...]
    passed: bool
    escalation: object | None = None  # EscalationDecision (avoids circular import)

    @property
    def triggered_rules(self) -> list[RuleEvaluation]:
        """Return only the evaluations that triggered."""
        return [e for e in self.evaluations if e.triggered]

    @property
    def warnings(self) -> list[RuleEvaluation]:
        """Return evaluations with WARN verdict."""
        return [e for e in self.evaluations if e.verdict == RuleVerdict.WARN]

    @property
    def failures(self) -> list[RuleEvaluation]:
        """Return evaluations with FAIL verdict."""
        return [e for e in self.evaluations if e.verdict == RuleVerdict.FAIL]


@dataclass
class CooldownState:
    """Tracks when guardrail rules last fired, scoped by rule_id and optional scope key."""

    _last_fired: dict[str, float] = field(default_factory=dict)

    def _key(self, rule_id: str, scope_key: str) -> str:
        return f"{rule_id}:{scope_key}" if scope_key else rule_id

    def in_cooldown(
        self,
        rule_id: str,
        cooldown_seconds: int,
        now: float,
        scope_key: str = "",
    ) -> bool:
        """Return True if the rule is still in its cooldown window."""
        if cooldown_seconds <= 0:
            return False
        key = self._key(rule_id, scope_key)
        last = self._last_fired.get(key)
        if last is None:
            return False
        return (now - last) < cooldown_seconds

    def record(self, rule_id: str, now: float, scope_key: str = "") -> None:
        """Record that a rule fired at the given timestamp."""
        self._last_fired[self._key(rule_id, scope_key)] = now
