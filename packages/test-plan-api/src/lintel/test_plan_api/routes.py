"""Test plan CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.test_plan_api.types import TestCase, TestCasePriority, TestPlan

if TYPE_CHECKING:
    from lintel.test_plan_api.store import InMemoryTestPlanStore

router = APIRouter()

test_plan_store_provider: StoreProvider[InMemoryTestPlanStore] = StoreProvider()


class TestCaseRequest(BaseModel):
    """Request body for a test case."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: str = ""
    steps: list[str] = []
    expected_result: str = ""
    priority: TestCasePriority = TestCasePriority.MEDIUM


class CreateTestPlanRequest(BaseModel):
    """Request body for creating a test plan."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str = ""
    title: str
    description: str = ""
    test_cases: list[TestCaseRequest] = []
    coverage_targets: list[str] = []


class UpdateTestPlanRequest(BaseModel):
    """Request body for updating a test plan."""

    title: str | None = None
    description: str | None = None
    project_id: str | None = None
    test_cases: list[TestCaseRequest] | None = None
    coverage_targets: list[str] | None = None


def _plan_to_dict(plan: TestPlan) -> dict[str, Any]:
    data = asdict(plan)
    data["test_cases"] = [{**asdict(tc), "steps": list(tc.steps)} for tc in plan.test_cases]
    data["coverage_targets"] = list(plan.coverage_targets)
    return data


def _request_to_test_case(req: TestCaseRequest) -> TestCase:
    return TestCase(
        id=req.id,
        name=req.name,
        description=req.description,
        steps=tuple(req.steps),
        expected_result=req.expected_result,
        priority=req.priority,
    )


@router.post("/test-plans", status_code=201)
async def create_test_plan(
    body: CreateTestPlanRequest,
    store: InMemoryTestPlanStore = Depends(test_plan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Test plan already exists")
    now = datetime.now(tz=UTC).isoformat()
    plan = TestPlan(
        id=body.id,
        project_id=body.project_id,
        title=body.title,
        description=body.description,
        test_cases=tuple(_request_to_test_case(tc) for tc in body.test_cases),
        coverage_targets=tuple(body.coverage_targets),
        created_at=now,
        updated_at=now,
    )
    await store.add(plan)
    return _plan_to_dict(plan)


@router.get("/test-plans")
async def list_test_plans(
    store: InMemoryTestPlanStore = Depends(test_plan_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    plans = await store.list_all()
    return [_plan_to_dict(p) for p in plans]


@router.get("/test-plans/{plan_id}")
async def get_test_plan(
    plan_id: str,
    store: InMemoryTestPlanStore = Depends(test_plan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Test plan not found")
    return _plan_to_dict(plan)


@router.patch("/test-plans/{plan_id}")
async def update_test_plan(
    plan_id: str,
    body: UpdateTestPlanRequest,
    store: InMemoryTestPlanStore = Depends(test_plan_store_provider),  # noqa: B008
) -> dict[str, Any]:
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Test plan not found")
    updates: dict[str, Any] = body.model_dump(exclude_none=True)
    if "test_cases" in updates:
        updates["test_cases"] = tuple(_request_to_test_case(tc) for tc in body.test_cases or [])
    if "coverage_targets" in updates:
        updates["coverage_targets"] = tuple(updates["coverage_targets"])
    updates["updated_at"] = datetime.now(tz=UTC).isoformat()
    current = asdict(plan)
    current.update(updates)
    updated = TestPlan(**current)
    await store.update(updated)
    return _plan_to_dict(updated)


@router.delete("/test-plans/{plan_id}", status_code=204)
async def delete_test_plan(
    plan_id: str,
    store: InMemoryTestPlanStore = Depends(test_plan_store_provider),  # noqa: B008
) -> None:
    plan = await store.get(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Test plan not found")
    await store.remove(plan_id)
