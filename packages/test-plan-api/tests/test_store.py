"""Tests for InMemoryTestPlanStore."""

from lintel.test_plan_api.store import InMemoryTestPlanStore
from lintel.test_plan_api.types import TestCase, TestCasePriority, TestPlan


class TestInMemoryTestPlanStore:
    async def test_add_and_get(self) -> None:
        store = InMemoryTestPlanStore()
        plan = TestPlan(id="tp-1", title="Login tests")
        await store.add(plan)
        result = await store.get("tp-1")
        assert result is not None
        assert result.title == "Login tests"

    async def test_get_returns_none_when_not_found(self) -> None:
        store = InMemoryTestPlanStore()
        result = await store.get("nonexistent")
        assert result is None

    async def test_list_all_empty(self) -> None:
        store = InMemoryTestPlanStore()
        result = await store.list_all()
        assert result == []

    async def test_list_all_returns_plans(self) -> None:
        store = InMemoryTestPlanStore()
        await store.add(TestPlan(id="tp-1", title="Plan 1"))
        await store.add(TestPlan(id="tp-2", title="Plan 2"))
        result = await store.list_all()
        assert len(result) == 2

    async def test_update(self) -> None:
        store = InMemoryTestPlanStore()
        plan = TestPlan(id="tp-1", title="Old title")
        await store.add(plan)
        updated = TestPlan(id="tp-1", title="New title")
        await store.update(updated)
        result = await store.get("tp-1")
        assert result is not None
        assert result.title == "New title"

    async def test_remove(self) -> None:
        store = InMemoryTestPlanStore()
        await store.add(TestPlan(id="tp-1", title="Plan"))
        await store.remove("tp-1")
        assert await store.get("tp-1") is None

    async def test_plan_with_test_cases(self) -> None:
        store = InMemoryTestPlanStore()
        tc = TestCase(
            id="tc-1",
            name="Login success",
            steps=("Open login page", "Enter credentials", "Click login"),
            expected_result="User is logged in",
            priority=TestCasePriority.HIGH,
        )
        plan = TestPlan(id="tp-1", title="Auth tests", test_cases=(tc,))
        await store.add(plan)
        result = await store.get("tp-1")
        assert result is not None
        assert len(result.test_cases) == 1
        assert result.test_cases[0].name == "Login success"
        assert result.test_cases[0].priority == TestCasePriority.HIGH
