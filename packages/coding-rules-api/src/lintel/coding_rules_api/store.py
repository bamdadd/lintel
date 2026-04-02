"""In-memory stores for coding rules and violations."""

from __future__ import annotations

from dataclasses import asdict
import fnmatch
from typing import Any

from lintel.domain.types import CodingRule, RuleViolation


def _rule_to_dict(rule: CodingRule) -> dict[str, Any]:
    """Convert a CodingRule dataclass to a JSON-friendly dict."""
    return asdict(rule)


def _violation_to_dict(violation: RuleViolation) -> dict[str, Any]:
    """Convert a RuleViolation dataclass to a JSON-friendly dict."""
    return asdict(violation)


class InMemoryCodingRuleStore:
    """Simple in-memory store for coding rules."""

    def __init__(self) -> None:
        self._rules: dict[str, CodingRule] = {}

    async def get(self, rule_id: str) -> dict[str, Any] | None:
        rule = self._rules.get(rule_id)
        if rule is None:
            return None
        return _rule_to_dict(rule)

    async def list_all(self) -> list[dict[str, Any]]:
        return [_rule_to_dict(r) for r in self._rules.values()]

    async def add(self, rule: CodingRule) -> dict[str, Any]:
        self._rules[rule.rule_id] = rule
        return _rule_to_dict(rule)

    async def update(self, rule_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        rule = self._rules.get(rule_id)
        if rule is None:
            return None
        data = asdict(rule)
        data.update(updates)
        updated = CodingRule(**data)
        self._rules[rule_id] = updated
        return _rule_to_dict(updated)

    async def remove(self, rule_id: str) -> bool:
        if rule_id not in self._rules:
            return False
        del self._rules[rule_id]
        return True

    def match_path(self, file_path: str) -> list[dict[str, Any]]:
        """Return active rules whose scope matches the given file path."""
        matched: list[CodingRule] = []
        for rule in self._rules.values():
            if not rule.active:
                continue
            dir_match = fnmatch.fnmatch(file_path, rule.scope.directory_pattern)
            file_match = fnmatch.fnmatch(
                file_path.rsplit("/", 1)[-1] if "/" in file_path else file_path,
                rule.scope.file_pattern,
            )
            if dir_match and file_match:
                matched.append(rule)
        return [_rule_to_dict(r) for r in matched]


class InMemoryRuleViolationStore:
    """Simple in-memory store for rule violations."""

    def __init__(self) -> None:
        self._violations: dict[str, RuleViolation] = {}

    async def get(self, violation_id: str) -> dict[str, Any] | None:
        v = self._violations.get(violation_id)
        if v is None:
            return None
        return _violation_to_dict(v)

    async def list_all(
        self,
        *,
        rule_id: str | None = None,
        pipeline_run_id: str | None = None,
        resolved: bool | None = None,
    ) -> list[dict[str, Any]]:
        results = list(self._violations.values())
        if rule_id is not None:
            results = [v for v in results if v.rule_id == rule_id]
        if pipeline_run_id is not None:
            results = [v for v in results if v.pipeline_run_id == pipeline_run_id]
        if resolved is not None:
            results = [v for v in results if v.resolved == resolved]
        return [_violation_to_dict(v) for v in results]

    async def add(self, violation: RuleViolation) -> dict[str, Any]:
        self._violations[violation.violation_id] = violation
        return _violation_to_dict(violation)

    async def update(
        self,
        violation_id: str,
        updates: dict[str, Any],
    ) -> dict[str, Any] | None:
        v = self._violations.get(violation_id)
        if v is None:
            return None
        data = asdict(v)
        data.update(updates)
        updated = RuleViolation(**data)
        self._violations[violation_id] = updated
        return _violation_to_dict(updated)
