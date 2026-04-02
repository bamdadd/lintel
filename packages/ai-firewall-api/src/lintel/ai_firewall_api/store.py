"""In-memory firewall stores."""

from __future__ import annotations

from dataclasses import asdict
import fnmatch
from typing import Any

from lintel.domain.types import FirewallAction, FirewallLogEntry, FirewallRule


def _rule_to_dict(rule: FirewallRule) -> dict[str, Any]:
    """Convert a FirewallRule dataclass to a JSON-friendly dict."""
    d = asdict(rule)
    d["agent_roles"] = list(rule.agent_roles)
    return d


def _log_to_dict(entry: FirewallLogEntry) -> dict[str, Any]:
    """Convert a FirewallLogEntry dataclass to a JSON-friendly dict."""
    return asdict(entry)


class InMemoryFirewallRuleStore:
    """Simple in-memory store for firewall rules."""

    def __init__(self) -> None:
        self._rules: dict[str, FirewallRule] = {}

    async def get(self, rule_id: str) -> dict[str, Any] | None:
        rule = self._rules.get(rule_id)
        if rule is None:
            return None
        return _rule_to_dict(rule)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_rule_to_dict(r) for r in self._rules.values()]

    async def add(self, rule: FirewallRule) -> dict[str, Any]:
        self._rules[rule.rule_id] = rule
        return _rule_to_dict(rule)

    async def update(self, rule_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        rule = self._rules.get(rule_id)
        if rule is None:
            return None
        data = asdict(rule)
        data.update(updates)
        if "agent_roles" in updates:
            data["agent_roles"] = tuple(updates["agent_roles"])
        elif isinstance(data["agent_roles"], list):
            data["agent_roles"] = tuple(data["agent_roles"])
        updated = FirewallRule(**data)
        self._rules[rule_id] = updated
        return _rule_to_dict(updated)

    async def remove(self, rule_id: str) -> bool:
        if rule_id not in self._rules:
            return False
        del self._rules[rule_id]
        return True

    def check_url(self, url: str, agent_role: str) -> tuple[FirewallAction, str | None]:
        """Check a URL against active rules. Returns (action, matching_rule_id)."""
        matching: list[FirewallRule] = []
        for rule in self._rules.values():
            if not rule.active:
                continue
            if rule.agent_roles and agent_role not in rule.agent_roles:
                continue
            if fnmatch.fnmatch(url, rule.pattern):
                matching.append(rule)
        if not matching:
            return FirewallAction.ALLOW, None
        # Highest priority (lowest number) wins
        best = min(matching, key=lambda r: r.priority)
        return best.action, best.rule_id


class InMemoryFirewallLogStore:
    """Simple in-memory store for firewall log entries."""

    def __init__(self) -> None:
        self._logs: list[FirewallLogEntry] = []

    async def add(self, entry: FirewallLogEntry) -> dict[str, Any]:
        self._logs.append(entry)
        return _log_to_dict(entry)

    async def list_all(
        self,
        *,
        agent_id: str | None = None,
        action: str | None = None,
        blocked: bool | None = None,
    ) -> list[dict[str, Any]]:
        results = self._logs
        if agent_id is not None:
            results = [e for e in results if e.agent_id == agent_id]
        if action is not None:
            results = [e for e in results if e.action_taken.value == action]
        if blocked is not None:
            results = [e for e in results if e.blocked == blocked]
        return [_log_to_dict(e) for e in results]
