"""In-memory store for cross-repo implementation plans."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class PlanStatus(StrEnum):
    draft = "draft"
    executing = "executing"
    completed = "completed"
    failed = "failed"


@dataclasses.dataclass
class RepoChange:
    repository_id: str = ""
    description: str = ""
    file_patterns: list[str] = dataclasses.field(default_factory=list)
    depends_on: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class CrossRepoPlan:
    plan_id: str = dataclasses.field(default_factory=lambda: uuid4().hex)
    title: str = ""
    description: str = ""
    repositories: list[str] = dataclasses.field(default_factory=list)
    changes: list[dict[str, object]] = dataclasses.field(default_factory=list)
    status: str = "draft"
    project_id: str = ""
    created_at: str = dataclasses.field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    started_at: str | None = None
    completed_at: str | None = None


class InMemoryCrossRepoPlanStore:
    """Simple in-memory store for cross-repo implementation plans."""

    def __init__(self) -> None:
        self._plans: dict[str, CrossRepoPlan] = {}

    async def add(self, plan: CrossRepoPlan) -> None:
        if plan.plan_id in self._plans:
            msg = f"Plan {plan.plan_id} already exists"
            raise KeyError(msg)
        self._plans[plan.plan_id] = plan

    async def get(self, plan_id: str) -> CrossRepoPlan | None:
        return self._plans.get(plan_id)

    async def list_all(self, status: str | None = None) -> list[CrossRepoPlan]:
        items = list(self._plans.values())
        if status is not None:
            items = [p for p in items if p.status == status]
        return items

    async def update(self, plan_id: str, fields: dict[str, object]) -> CrossRepoPlan | None:
        plan = self._plans.get(plan_id)
        if plan is None:
            return None
        for key, value in fields.items():
            if hasattr(plan, key):
                object.__setattr__(plan, key, value)
        return plan

    async def remove(self, plan_id: str) -> None:
        if plan_id not in self._plans:
            msg = f"Plan {plan_id} not found"
            raise KeyError(msg)
        del self._plans[plan_id]
