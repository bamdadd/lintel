"""Project CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.container import AppContainer
from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.data_models import ProjectData
from lintel.contracts.events import ProjectCreated, ProjectRemoved, ProjectUpdated
from lintel.contracts.types import Project, ProjectStatus

router = APIRouter()


class ProjectStore:
    """In-memory project store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, project: Project) -> None:
        data = asdict(project)
        # Convert tuples to lists for JSON compat
        for key in ("repo_ids", "credential_ids"):
            if isinstance(data.get(key), tuple):
                data[key] = list(data[key])
        validated = ProjectData.model_validate(data)
        self._data[project.project_id] = validated.model_dump()

    async def get(self, project_id: str) -> dict[str, Any] | None:
        return self._data.get(project_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def update(self, project_id: str, data: dict[str, Any]) -> None:
        # Convert tuples to lists before validation
        for key in ("repo_ids", "credential_ids"):
            if isinstance(data.get(key), tuple):
                data[key] = list(data[key])
        validated = ProjectData.model_validate(data)
        self._data[project_id] = validated.model_dump()

    async def remove(self, project_id: str) -> None:
        self._data.pop(project_id, None)


def get_project_store(request: Request) -> ProjectStore:
    """Get project store from app state."""
    return request.app.state.project_store  # type: ignore[no-any-return]


class CreateProjectRequest(BaseModel):
    project_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    repo_ids: list[str] = []
    default_branch: str = "main"
    credential_ids: list[str] = []
    status: ProjectStatus = ProjectStatus.ACTIVE


class UpdateProjectRequest(BaseModel):
    name: str | None = None
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


@router.post("/projects", status_code=201)
@inject
async def create_project(
    request: Request,
    body: CreateProjectRequest,
    store: ProjectStore = Depends(Provide[AppContainer.project_store]),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.project_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Project already exists")
    project = Project(
        project_id=body.project_id,
        name=body.name,
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
@inject
async def list_projects(
    store: ProjectStore = Depends(Provide[AppContainer.project_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/projects/{project_id}")
@inject
async def get_project(
    project_id: str,
    store: ProjectStore = Depends(Provide[AppContainer.project_store]),  # noqa: B008
) -> dict[str, Any]:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return item


@router.patch("/projects/{project_id}")
@inject
async def update_project(
    request: Request,
    project_id: str,
    body: UpdateProjectRequest,
    store: ProjectStore = Depends(Provide[AppContainer.project_store]),  # noqa: B008
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
@inject
async def remove_project(
    request: Request,
    project_id: str,
    store: ProjectStore = Depends(Provide[AppContainer.project_store]),  # noqa: B008
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
