"""In-memory workflow ACL store."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.domain.types import AclRule


class InMemoryAclRuleStore:
    """Simple in-memory store for workflow ACL rules."""

    def __init__(self) -> None:
        self._rules: dict[str, dict[str, Any]] = {}

    async def add(self, rule: AclRule) -> dict[str, Any]:
        data = asdict(rule)
        data["workflow_types"] = list(rule.workflow_types)
        self._rules[rule.rule_id] = data
        return data

    async def get(self, rule_id: str) -> dict[str, Any] | None:
        return self._rules.get(rule_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._rules.values())

    async def remove(self, rule_id: str) -> bool:
        if rule_id not in self._rules:
            return False
        del self._rules[rule_id]
        return True

    def check(
        self,
        connection_id: str,
        workflow_type: str,
        project_id: str = "",
    ) -> tuple[bool, str]:
        """Check if a connection is allowed to trigger a workflow.

        Returns (allowed, reason).
        """
        matching: list[dict[str, Any]] = []
        for rule in self._rules.values():
            if rule.get("connection_id") != connection_id:
                continue
            wf_types = rule.get("workflow_types", [])
            if wf_types and workflow_type not in wf_types:
                continue
            rule_project = rule.get("project_id", "")
            if rule_project and project_id and rule_project != project_id:
                continue
            matching.append(rule)

        if not matching:
            return True, "no_matching_rules"

        # Any deny rule blocks
        for rule in matching:
            if rule.get("effect") == "deny":
                return False, f"denied_by_rule:{rule['rule_id']}"

        # Explicit allow found
        return True, "allowed_by_rule"
