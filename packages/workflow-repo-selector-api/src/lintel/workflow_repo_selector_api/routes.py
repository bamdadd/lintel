"""Workflow repo selector API routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.workflow_repo_selector_api.selector import RepoSelector
from lintel.workflow_repo_selector_api.store import (
    InMemoryRepoDescriptionStore as _Store,
)
from lintel.workflow_repo_selector_api.store import RepoDescription

router = APIRouter()

repo_description_store_provider: StoreProvider[_Store] = StoreProvider()

_selector = RepoSelector()


class SelectionRequest(BaseModel):
    description: str
    project_id: str = ""


class RegisterRepoRequest(BaseModel):
    repo_id: str | None = None
    name: str
    project_id: str = ""
    description: str = ""
    languages: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    service_type: str = ""


@router.post("/workflow-repo-selector/select")
async def select_repos(
    body: SelectionRequest,
    store: Annotated[_Store, Depends(repo_description_store_provider)],
) -> dict[str, Any]:
    repos = store.get_all_repos()
    selections = _selector.select(repos, body.description, body.project_id)
    return {"selections": [asdict(s) for s in selections]}


@router.post("/workflow-repo-selector/repos", status_code=201)
async def register_repo(
    body: RegisterRepoRequest,
    store: Annotated[_Store, Depends(repo_description_store_provider)],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "name": body.name,
        "project_id": body.project_id,
        "description": body.description,
        "languages": body.languages,
        "tags": body.tags,
        "service_type": body.service_type,
    }
    if body.repo_id is not None:
        kwargs["repo_id"] = body.repo_id
    repo = RepoDescription(**kwargs)
    try:
        result = await store.add(repo)
    except ValueError:
        raise HTTPException(status_code=409, detail="Repo already exists")  # noqa: B904
    return result


@router.get("/workflow-repo-selector/repos")
async def list_repos(
    store: Annotated[_Store, Depends(repo_description_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    return await store.list_all(project_id=project_id)


@router.delete("/workflow-repo-selector/repos/{repo_id}", status_code=204)
async def delete_repo(
    repo_id: str,
    store: Annotated[_Store, Depends(repo_description_store_provider)],
) -> None:
    if not await store.remove(repo_id):
        raise HTTPException(status_code=404, detail="Repo not found")
