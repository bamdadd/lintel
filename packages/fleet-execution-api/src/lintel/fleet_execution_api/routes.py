"""Fleet execution endpoints — run agents across hundreds of repos."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.fleet_execution_api.store import (
    FleetRun,
    FleetRunStatus,
    InMemoryFleetRunStore,
    RepoRun,
    _fleet_to_dict,
)

router = APIRouter()

fleet_run_store_provider: StoreProvider[InMemoryFleetRunStore] = StoreProvider()


class CreateFleetRunRequest(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    repo_ids: list[str]
    agent_definition_id: str = ""
    workflow_definition_id: str = ""


@router.post("/fleet/runs", status_code=201)
async def create_fleet_run(
    body: CreateFleetRunRequest,
    store: InMemoryFleetRunStore = Depends(fleet_run_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Start a fleet run across a list of repositories."""
    existing = await store.get(body.run_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Fleet run already exists")
    if not body.repo_ids:
        raise HTTPException(status_code=422, detail="repo_ids must not be empty")
    repo_runs = tuple(RepoRun(repo_id=rid) for rid in body.repo_ids)
    run = FleetRun(
        run_id=body.run_id,
        name=body.name,
        repo_ids=tuple(body.repo_ids),
        agent_definition_id=body.agent_definition_id,
        workflow_definition_id=body.workflow_definition_id,
        status=FleetRunStatus.RUNNING,
        repo_runs=repo_runs,
    )
    await store.add(run)
    return _fleet_to_dict(run)


@router.get("/fleet/runs")
async def list_fleet_runs(
    store: InMemoryFleetRunStore = Depends(fleet_run_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all fleet runs."""
    runs = await store.list_all()
    return [_fleet_to_dict(r) for r in runs]


@router.get("/fleet/runs/{run_id}")
async def get_fleet_run(
    run_id: str,
    store: InMemoryFleetRunStore = Depends(fleet_run_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get fleet run status including per-repo breakdown."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Fleet run not found")
    return _fleet_to_dict(run)


@router.post("/fleet/runs/{run_id}/cancel")
async def cancel_fleet_run(
    run_id: str,
    store: InMemoryFleetRunStore = Depends(fleet_run_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Cancel a running fleet run."""
    run = await store.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Fleet run not found")
    if run.status not in (FleetRunStatus.PENDING, FleetRunStatus.RUNNING):
        raise HTTPException(status_code=409, detail="Fleet run is not cancellable")
    cancelled = FleetRun(
        run_id=run.run_id,
        name=run.name,
        repo_ids=run.repo_ids,
        agent_definition_id=run.agent_definition_id,
        workflow_definition_id=run.workflow_definition_id,
        status=FleetRunStatus.CANCELLED,
        repo_runs=run.repo_runs,
        created_at=run.created_at,
        cancelled_at=datetime.now(UTC).isoformat(),
    )
    await store.update(cancelled)
    return _fleet_to_dict(cancelled)
