"""In-memory test plan store."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.test_plan_api.types import TestPlan


class InMemoryTestPlanStore:
    """Simple in-memory store for test plans."""

    def __init__(self) -> None:
        self._plans: dict[str, TestPlan] = {}

    async def add(self, plan: TestPlan) -> None:
        self._plans[plan.id] = plan

    async def get(self, plan_id: str) -> TestPlan | None:
        return self._plans.get(plan_id)

    async def list_all(self) -> list[TestPlan]:
        return list(self._plans.values())

    async def update(self, plan: TestPlan) -> None:
        self._plans[plan.id] = plan

    async def remove(self, plan_id: str) -> None:
        del self._plans[plan_id]
