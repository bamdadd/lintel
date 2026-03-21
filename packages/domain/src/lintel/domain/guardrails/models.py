"""Domain models for guardrail rules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class GuardrailAction(StrEnum):
    WARN = "WARN"
    BLOCK = "BLOCK"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"


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
