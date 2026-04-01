"""Repository interface for guardrail rules."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from lintel.domain.guardrails.models import GuardrailRule


class RuleRepository(Protocol):
    """Protocol for loading guardrail rules from storage."""

    async def list_enabled(self) -> list[GuardrailRule]: ...

    async def list_by_event_type(self, event_type: str) -> list[GuardrailRule]: ...

    async def get(self, rule_id: str) -> GuardrailRule | None: ...

    async def upsert(self, rule: GuardrailRule) -> None: ...

    async def delete(self, rule_id: str) -> bool: ...
