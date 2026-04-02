"""Project CRUD endpoints."""

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import ProjectCreated, ProjectRemoved, ProjectUpdated
from lintel.domain.types import Project, ProjectStatus
from lintel.projects_api.store import ProjectStore

router = APIRouter()

project_store_provider = StoreProvider()


class CreateProjectRequest(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str = ""
    repo_ids: list[str] = []
    default_branch: str = "main"
    credential_ids: list[str] = []
    status: ProjectStatus = ProjectStatus.ACTIVE


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    repo_ids: list[str] | None = None
    default_branch: str | None = None
    credential_ids: list[str] | None = None
    status: ProjectStatus | None = None
    ai_provider_id: str | None = None
    model_id: str | None = None
    workflow_definition_id: str | None = None
    channel_id: str | None = None
    workspace_id: str | None = None
    compliance_config: dict[str, object] | None = None


class PrincipleRequest(BaseModel):
    """Request body for creating/updating an engineering principle."""

    name: str
    description: str = ""
    category: str = "general"


@router.post("/projects", status_code=201)
async def create_project(
    request: Request,
    body: CreateProjectRequest,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.project_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Project already exists")
    project = Project(
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        repo_ids=tuple(body.repo_ids),
        default_branch=body.default_branch,
        credential_ids=tuple(body.credential_ids),
        status=body.status,
    )
    await store.add(project)
    await dispatch_event(
        request,
        ProjectCreated(payload={"resource_id": body.project_id, "name": body.name}),
        stream_id=f"project:{body.project_id}",
    )
    result = await store.get(body.project_id)
    return result  # type: ignore[return-value]


@router.get("/projects")
async def list_projects(
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return item


@router.patch("/projects/{project_id}")
async def update_project(
    request: Request,
    project_id: str,
    body: UpdateProjectRequest,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    updates = body.model_dump(exclude_none=True)
    merged = {**item, **updates}
    await store.update(project_id, merged)
    await dispatch_event(
        request,
        ProjectUpdated(payload={"resource_id": project_id, "fields": list(updates.keys())}),
        stream_id=f"project:{project_id}",
    )
    result = await store.get(project_id)
    return result  # type: ignore[return-value]


@router.delete("/projects/{project_id}", status_code=204)
async def remove_project(
    request: Request,
    project_id: str,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> None:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await store.remove(project_id)
    await dispatch_event(
        request,
        ProjectRemoved(payload={"resource_id": project_id, "name": item.get("name", "")}),
        stream_id=f"project:{project_id}",
    )


# --- Principles sub-resource ---


async def _get_project_or_404(
    project_id: str,
    store: ProjectStore,
) -> dict[str, Any]:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return item


@router.get("/projects/{project_id}/principles")
async def list_principles(
    project_id: str,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    project = await _get_project_or_404(project_id, store)
    return project.get("principles", [])  # type: ignore[no-any-return]


@router.post("/projects/{project_id}/principles", status_code=201)
async def create_principle(
    request: Request,
    project_id: str,
    body: PrincipleRequest,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> dict[str, Any]:
    project = await _get_project_or_404(project_id, store)
    principle: dict[str, Any] = {
        "principle_id": str(uuid4()),
        "name": body.name,
        "description": body.description,
        "category": body.category,
    }
    principles: list[dict[str, Any]] = project.get("principles", [])  # type: ignore[assignment]
    principles.append(principle)
    project["principles"] = principles
    await store.update(project_id, project)
    await dispatch_event(
        request,
        ProjectUpdated(
            payload={"resource_id": project_id, "fields": ["principles"]},
        ),
        stream_id=f"project:{project_id}",
    )
    return principle


@router.get("/projects/{project_id}/principles/{principle_id}")
async def get_principle(
    project_id: str,
    principle_id: str,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> dict[str, Any]:
    project = await _get_project_or_404(project_id, store)
    principles: list[dict[str, Any]] = project.get("principles", [])  # type: ignore[assignment]
    for p in principles:
        if p["principle_id"] == principle_id:
            return p
    raise HTTPException(status_code=404, detail="Principle not found")


@router.patch("/projects/{project_id}/principles/{principle_id}")
async def update_principle(
    request: Request,
    project_id: str,
    principle_id: str,
    body: PrincipleRequest,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> dict[str, Any]:
    project = await _get_project_or_404(project_id, store)
    principles: list[dict[str, Any]] = project.get("principles", [])  # type: ignore[assignment]
    for p in principles:
        if p["principle_id"] == principle_id:
            p["name"] = body.name
            p["description"] = body.description
            p["category"] = body.category
            project["principles"] = principles
            await store.update(project_id, project)
            await dispatch_event(
                request,
                ProjectUpdated(
                    payload={"resource_id": project_id, "fields": ["principles"]},
                ),
                stream_id=f"project:{project_id}",
            )
            return p
    raise HTTPException(status_code=404, detail="Principle not found")


@router.delete("/projects/{project_id}/principles/{principle_id}", status_code=204)
async def delete_principle(
    request: Request,
    project_id: str,
    principle_id: str,
    store: ProjectStore = Depends(project_store_provider),  # noqa: B008
) -> None:
    project = await _get_project_or_404(project_id, store)
    principles: list[dict[str, Any]] = project.get("principles", [])  # type: ignore[assignment]
    new_principles = [p for p in principles if p["principle_id"] != principle_id]
    if len(new_principles) == len(principles):
        raise HTTPException(status_code=404, detail="Principle not found")
    project["principles"] = new_principles
    await store.update(project_id, project)
    await dispatch_event(
        request,
        ProjectUpdated(
            payload={"resource_id": project_id, "fields": ["principles"]},
        ),
        stream_id=f"project:{project_id}",
    )
