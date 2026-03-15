"""In-memory notification rule store."""

from lintel.domain.types import NotificationRule


class NotificationRuleStore:
    """In-memory store for notification rules."""

    def __init__(self) -> None:
        self._rules: dict[str, NotificationRule] = {}

    async def add(self, rule: NotificationRule) -> None:
        self._rules[rule.rule_id] = rule

    async def get(self, rule_id: str) -> NotificationRule | None:
        return self._rules.get(rule_id)

    async def list_all(self, *, project_id: str | None = None) -> list[NotificationRule]:
        rules = list(self._rules.values())
        if project_id is not None:
            rules = [r for r in rules if r.project_id == project_id]
        return rules

    async def update(self, rule: NotificationRule) -> None:
        self._rules[rule.rule_id] = rule

    async def remove(self, rule_id: str) -> None:
        del self._rules[rule_id]
