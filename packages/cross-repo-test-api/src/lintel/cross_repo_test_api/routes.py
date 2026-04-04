"""Cross-repo test run endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, HTTPException
import pydantic

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.cross_repo_test_api.store import InMemoryTestRunStore

router = APIRouter()

test_run_store_provider: StoreProvider[InMemoryTestRunStore] = StoreProvider()


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateTestRunRequest(pydantic.BaseModel):
    run_id: str | None = None
    repositories: list[str]
    project_id: str = ""
    triggered_by: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/cross-repo-tests/runs", status_code=201)
async def create_test_run(
    body: CreateTestRunRequest,
    store: InMemoryTestRunStore = Depends(test_run_store_provider),  # noqa: B008
) -> dict[str, Any]:
    from lintel.cross_repo_test_api.store import TestRun

    kwargs: dict[str, Any] = {
        "repositories": body.repositories,
        "project_id": body.project_id,
        "triggered_by": body.triggered_by,
        "status": "pending",
    }
    if body.run_id is not None:
        kwargs["run_id"] = body.run_id
    run = TestRun(**kwargs)
    try:
        await store.add(run)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return asdict(run)


@router.get("/cross-repo-tests/runs")
async def list_test_runs(
    status: str | None = None,
    store: InMemoryTestRunStore = Depends(test_run_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    runs = await store.list_all(status=status)
    return [asdict(r) for r in runs]


@router.get("/cross-repo-tests/runs/{run_id}")
async def get_test_run(
    run_id: str,
    store: InMemoryTestRunStore = Depends(test_run_store_provider),  # noqa: B008
) -> dict[str, Any]:
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Test run not found")
    return asdict(run)
