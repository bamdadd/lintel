"""In-memory store for channel message routing rules."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from uuid import uuid4


@dataclasses.dataclass
class RoutingRule:
    """A rule that maps a connection + pattern to a workflow definition."""

    rule_id: str = dataclasses.field(default_factory=lambda: uuid4().hex)
    connection_id: str = ""
    channel_pattern: str = "*"
    message_pattern: str = ""
    workflow_definition_id: str = ""
    priority: int = 0
    enabled: bool = True
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )


class InMemoryRoutingRuleStore:
    """Simple in-memory store for routing rules."""

    def __init__(self) -> None:
        self._rules: dict[str, RoutingRule] = {}

    async def add(self, rule: RoutingRule) -> None:
        if rule.rule_id in self._rules:
            msg = f"Routing rule {rule.rule_id} already exists"
            raise KeyError(msg)
        self._rules[rule.rule_id] = rule

    async def get(self, rule_id: str) -> RoutingRule | None:
        return self._rules.get(rule_id)

    async def list_all(self, connection_id: str | None = None) -> list[RoutingRule]:
        items = list(self._rules.values())
        if connection_id is not None:
            items = [r for r in items if r.connection_id == connection_id]
        return items

    async def remove(self, rule_id: str) -> None:
        if rule_id not in self._rules:
            msg = f"Routing rule {rule_id} not found"
            raise KeyError(msg)
        del self._rules[rule_id]
