"""In-memory store for organisation security policies."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class PolicyScope(StrEnum):
    agent = "agent"
    sandbox = "sandbox"
    tool_use = "tool_use"
    data_access = "data_access"
    network = "network"


class PolicyAction(StrEnum):
    allow = "allow"
    deny = "deny"
    require_approval = "require_approval"


@dataclasses.dataclass
class OrgSecurityPolicy:
    policy_id: str = dataclasses.field(default_factory=lambda: uuid4().hex)
    name: str = ""
    description: str = ""
    scope: PolicyScope = PolicyScope.agent
    rules: list[dict[str, object]] = dataclasses.field(default_factory=list)
    action: PolicyAction = PolicyAction.deny
    enabled: bool = True
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(tz=UTC).isoformat())


@dataclasses.dataclass
class EvaluationResult:
    allowed: bool
    violations: list[dict[str, object]] = dataclasses.field(default_factory=list)


class InMemoryOrgSecurityPolicyStore:
    """Simple in-memory store for organisation security policies."""

    def __init__(self) -> None:
        self._policies: dict[str, OrgSecurityPolicy] = {}

    async def add(self, policy: OrgSecurityPolicy) -> None:
        self._policies[policy.policy_id] = policy

    async def get(self, policy_id: str) -> OrgSecurityPolicy | None:
        return self._policies.get(policy_id)

    async def list_all(self, scope: str | None = None) -> list[OrgSecurityPolicy]:
        items = list(self._policies.values())
        if scope is not None:
            items = [p for p in items if p.scope == scope]
        return items

    async def remove(self, policy_id: str) -> None:
        if policy_id not in self._policies:
            msg = f"Policy {policy_id} not found"
            raise KeyError(msg)
        del self._policies[policy_id]
