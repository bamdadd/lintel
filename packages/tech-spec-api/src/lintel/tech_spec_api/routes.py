"""Tech spec CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import TechSpecCreated, TechSpecRemoved, TechSpecUpdated
from lintel.domain.types import Milestone, TechSpec, TechSpecStatus

if TYPE_CHECKING:
    from lintel.tech_spec_api.store import InMemoryTechSpecStore

router = APIRouter()

tech_spec_store_provider: StoreProvider[InMemoryTechSpecStore] = StoreProvider()


class MilestoneModel(BaseModel):
    name: str
    description: str = ""
    estimated_effort: str = ""


class CreateTechSpecRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str
    problem_statement: str = ""
    proposed_solution: str = ""
    alternatives: list[str] = []
    dependencies: list[str] = []
    risks: list[str] = []
    milestones: list[MilestoneModel] = []
    status: TechSpecStatus = TechSpecStatus.DRAFT


class UpdateTechSpecRequest(BaseModel):
    title: str | None = None
    problem_statement: str | None = None
    proposed_solution: str | None = None
    alternatives: list[str] | None = None
    dependencies: list[str] | None = None
    risks: list[str] | None = None
    milestones: list[MilestoneModel] | None = None
    status: TechSpecStatus | None = None


def _spec_to_dict(spec: TechSpec) -> dict[str, Any]:
    data = asdict(spec)
    data["milestones"] = [asdict(m) for m in spec.milestones]
    data["alternatives"] = list(spec.alternatives)
    data["dependencies"] = list(spec.dependencies)
    data["risks"] = list(spec.risks)
    return data


def _build_milestones(models: list[MilestoneModel]) -> tuple[Milestone, ...]:
    return tuple(
        Milestone(
            name=m.name,
            description=m.description,
            estimated_effort=m.estimated_effort,
        )
        for m in models
    )


@router.post("/tech-specs", status_code=201)
async def create_tech_spec(
    body: CreateTechSpecRequest,
    request: Request,
    store: InMemoryTechSpecStore = Depends(tech_spec_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Tech spec already exists")
    now = datetime.now(UTC).isoformat()
    spec = TechSpec(
        id=body.id,
        project_id=body.project_id,
        title=body.title,
        problem_statement=body.problem_statement,
        proposed_solution=body.proposed_solution,
        alternatives=tuple(body.alternatives),
        dependencies=tuple(body.dependencies),
        risks=tuple(body.risks),
        milestones=_build_milestones(body.milestones),
        status=body.status,
        created_at=now,
        updated_at=now,
    )
    await store.add(spec)
    await dispatch_event(
        request,
        TechSpecCreated(payload={"resource_id": body.id, "title": body.title}),
        stream_id=f"tech-spec:{body.id}",
    )
    return _spec_to_dict(spec)


@router.get("/tech-specs")
async def list_tech_specs(
    project_id: str | None = None,
    store: InMemoryTechSpecStore = Depends(tech_spec_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    specs = await store.list_all(project_id=project_id)
    return [_spec_to_dict(s) for s in specs]


@router.get("/tech-specs/{spec_id}")
async def get_tech_spec(
    spec_id: str,
    store: InMemoryTechSpecStore = Depends(tech_spec_store_provider),  # noqa: B008
) -> dict[str, Any]:
    spec = await store.get(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Tech spec not found")
    return _spec_to_dict(spec)


@router.patch("/tech-specs/{spec_id}")
async def update_tech_spec(
    spec_id: str,
    body: UpdateTechSpecRequest,
    request: Request,
    store: InMemoryTechSpecStore = Depends(tech_spec_store_provider),  # noqa: B008
) -> dict[str, Any]:
    spec = await store.get(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Tech spec not found")
    updates = body.model_dump(exclude_none=True)
    if "milestones" in updates:
        updates["milestones"] = _build_milestones(body.milestones or [])
    if "alternatives" in updates:
        updates["alternatives"] = tuple(updates["alternatives"])
    if "dependencies" in updates:
        updates["dependencies"] = tuple(updates["dependencies"])
    if "risks" in updates:
        updates["risks"] = tuple(updates["risks"])
    now = datetime.now(UTC).isoformat()
    updates["updated_at"] = now
    updated = TechSpec(**{**asdict(spec), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        TechSpecUpdated(
            payload={"resource_id": spec_id, "fields": list(body.model_dump(exclude_none=True))}
        ),
        stream_id=f"tech-spec:{spec_id}",
    )
    return _spec_to_dict(updated)


@router.delete("/tech-specs/{spec_id}", status_code=204)
async def delete_tech_spec(
    spec_id: str,
    request: Request,
    store: InMemoryTechSpecStore = Depends(tech_spec_store_provider),  # noqa: B008
) -> None:
    spec = await store.get(spec_id)
    if spec is None:
        raise HTTPException(status_code=404, detail="Tech spec not found")
    await store.remove(spec_id)
    await dispatch_event(
        request,
        TechSpecRemoved(payload={"resource_id": spec_id, "title": spec.title}),
        stream_id=f"tech-spec:{spec_id}",
    )
