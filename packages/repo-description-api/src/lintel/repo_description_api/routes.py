"""Repository description editor endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import ProjectUpdated
from lintel.repo_description_api.store import InMemoryRepoDescriptionStore, RepoDescription

router = APIRouter()

repo_description_store_provider: StoreProvider = StoreProvider()


class PutDescriptionRequest(BaseModel):
    description: str


@router.put("/projects/{project_id}/repositories/{repo_id}/description")
async def put_repo_description(
    project_id: str,
    repo_id: str,
    body: PutDescriptionRequest,
    request: Request,
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> dict[str, Any]:
    entry = RepoDescription(
        project_id=project_id,
        repo_id=repo_id,
        description=body.description,
    )
    await store.put(entry)
    await dispatch_event(
        request,
        ProjectUpdated(
            payload={
                "resource_id": project_id,
                "fields": ["repo_descriptions"],
                "repo_id": repo_id,
            },
        ),
        stream_id=f"project:{project_id}",
    )
    return {"project_id": project_id, "repo_id": repo_id, "description": body.description}


@router.get("/projects/{project_id}/repositories/{repo_id}/description")
async def get_repo_description(
    project_id: str,
    repo_id: str,
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> dict[str, Any]:
    entry = await store.get(project_id, repo_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Description not found")
    return {"project_id": project_id, "repo_id": repo_id, "description": entry.description}


@router.get("/projects/{project_id}/repo-descriptions")
async def list_repo_descriptions(
    project_id: str,
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    entries = await store.list_by_project(project_id)
    return [
        {"project_id": e.project_id, "repo_id": e.repo_id, "description": e.description}
        for e in entries
    ]


@router.delete(
    "/projects/{project_id}/repositories/{repo_id}/description",
    status_code=204,
)
async def delete_repo_description(
    project_id: str,
    repo_id: str,
    request: Request,
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> None:
    entry = await store.get(project_id, repo_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="Description not found")
    await store.remove(project_id, repo_id)
    await dispatch_event(
        request,
        ProjectUpdated(
            payload={
                "resource_id": project_id,
                "fields": ["repo_descriptions"],
                "repo_id": repo_id,
            },
        ),
        stream_id=f"project:{project_id}",
    )
