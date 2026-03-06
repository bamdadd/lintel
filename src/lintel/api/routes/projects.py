"""Project CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import Project, ProjectStatus

router = APIRouter()


class ProjectStore:
    """In-memory project store."""

    def __init__(self) -> None:
        self._data: dict[str, dict[str, Any]] = {}

    async def add(self, project: Project) -> None:
        self._data[project.project_id] = asdict(project)

    async def get(self, project_id: str) -> dict[str, Any] | None:
        return self._data.get(project_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def update(self, project_id: str, data: dict[str, Any]) -> None:
        self._data[project_id] = data

    async def remove(self, project_id: str) -> None:
        self._data.pop(project_id, None)


def get_project_store(request: Request) -> ProjectStore:
    """Get project store from app state."""
    return request.app.state.project_store  # type: ignore[no-any-return]


def _to_response(data: dict[str, Any]) -> dict[str, Any]:
    """Convert tuple fields to lists for JSON serialisation."""
    out = dict(data)
    if isinstance(out.get("credential_ids"), tuple):
        out["credential_ids"] = list(out["credential_ids"])
    return out


class CreateProjectRequest(BaseModel):
    project_id: str
    name: str
    repo_id: str
    channel_id: str = ""
    workspace_id: str = ""
    workflow_definition_id: str = "feature_to_pr"
    default_branch: str = "main"
    credential_ids: list[str] = []
    ai_provider_id: str = ""
    status: ProjectStatus = ProjectStatus.ACTIVE


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    repo_id: str | None = None
    channel_id: str | None = None
    workspace_id: str | None = None
    workflow_definition_id: str | None = None
    default_branch: str | None = None
    credential_ids: list[str] | None = None
    ai_provider_id: str | None = None
    status: ProjectStatus | None = None


@router.post("/projects", status_code=201)
async def create_project(
    body: CreateProjectRequest,
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> dict[str, Any]:
    existing = await store.get(body.project_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Project already exists")
    project = Project(
        project_id=body.project_id,
        name=body.name,
        repo_id=body.repo_id,
        channel_id=body.channel_id,
        workspace_id=body.workspace_id,
        workflow_definition_id=body.workflow_definition_id,
        default_branch=body.default_branch,
        credential_ids=tuple(body.credential_ids),
        ai_provider_id=body.ai_provider_id,
        status=body.status,
    )
    await store.add(project)
    return _to_response(asdict(project))


@router.get("/projects")
async def list_projects(
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> list[dict[str, Any]]:
    items = await store.list_all()
    return [_to_response(item) for item in items]


@router.get("/projects/{project_id}")
async def get_project(
    project_id: str,
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> dict[str, Any]:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return _to_response(item)


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> dict[str, Any]:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    updates = body.model_dump(exclude_none=True)
    if "credential_ids" in updates:
        updates["credential_ids"] = tuple(updates["credential_ids"])
    merged = {**item, **updates}
    await store.update(project_id, merged)
    return _to_response(merged)


@router.delete("/projects/{project_id}", status_code=204)
async def remove_project(
    project_id: str,
    store: Annotated[ProjectStore, Depends(get_project_store)],
) -> None:
    item = await store.get(project_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await store.remove(project_id)
