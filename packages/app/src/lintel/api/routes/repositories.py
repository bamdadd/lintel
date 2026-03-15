"""Repository CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.container import AppContainer
from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.repos.events import RepositoryRegistered, RepositoryRemoved, RepositoryUpdated
from lintel.repos.repository_store import InMemoryRepositoryStore
from lintel.repos.types import Repository, RepoStatus

router = APIRouter()


def _gen_id() -> str:
    return str(uuid4())


class RegisterRepoRequest(BaseModel):
    repo_id: str = Field(default_factory=_gen_id)
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"


class UpdateRepoRequest(BaseModel):
    name: str | None = None
    default_branch: str | None = None
    owner: str | None = None
    status: RepoStatus | None = None


@router.post("/repositories", status_code=201)
@inject
async def register_repository(
    body: RegisterRepoRequest,
    request: Request,
    store: InMemoryRepositoryStore = Depends(Provide[AppContainer.repository_store]),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.repo_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Repository already exists")
    repo = Repository(
        repo_id=body.repo_id,
        name=body.name,
        url=body.url,
        default_branch=body.default_branch,
        owner=body.owner,
        provider=body.provider,
    )
    await store.add(repo)
    await dispatch_event(
        request,
        RepositoryRegistered(
            payload={"resource_id": body.repo_id, "name": body.name, "url": body.url}
        ),
        stream_id=f"repository:{body.repo_id}",
    )
    return asdict(repo)


@router.get("/repositories")
@inject
async def list_repositories(
    store: InMemoryRepositoryStore = Depends(Provide[AppContainer.repository_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    repos = await store.list_all()
    return [asdict(r) for r in repos]


@router.get("/repositories/{repo_id}")
@inject
async def get_repository(
    repo_id: str,
    store: InMemoryRepositoryStore = Depends(Provide[AppContainer.repository_store]),  # noqa: B008
) -> dict[str, Any]:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return asdict(repo)


@router.patch("/repositories/{repo_id}")
@inject
async def update_repository(
    repo_id: str,
    body: UpdateRepoRequest,
    request: Request,
    store: InMemoryRepositoryStore = Depends(Provide[AppContainer.repository_store]),  # noqa: B008
) -> dict[str, Any]:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    updates = body.model_dump(exclude_none=True)
    updated = Repository(**{**asdict(repo), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        RepositoryUpdated(payload={"resource_id": repo_id, "fields": list(updates.keys())}),
        stream_id=f"repository:{repo_id}",
    )
    return asdict(updated)


@router.delete("/repositories/{repo_id}", status_code=204)
@inject
async def remove_repository(
    repo_id: str,
    request: Request,
    store: InMemoryRepositoryStore = Depends(Provide[AppContainer.repository_store]),  # noqa: B008
) -> None:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    await store.remove(repo_id)
    await dispatch_event(
        request,
        RepositoryRemoved(payload={"resource_id": repo_id, "name": repo.name}),
        stream_id=f"repository:{repo_id}",
    )


@router.get("/repositories/{repo_id}/commits")
@inject
async def list_repository_commits(
    repo_id: str,
    branch: str | None = None,
    limit: int = 20,
    store: InMemoryRepositoryStore = Depends(Provide[AppContainer.repository_store]),  # noqa: B008
    repo_provider: Any = Depends(Provide[AppContainer.repo_provider]),  # noqa: B008, ANN401
) -> list[dict[str, Any]]:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo_provider is None:
        raise HTTPException(status_code=503, detail="Repository provider not configured")
    ref = branch or repo.default_branch
    result: list[dict[str, Any]] = await repo_provider.list_commits(repo.url, ref, limit)
    return result


@router.get("/repositories/{repo_id}/pull-requests")
@inject
async def list_repository_pull_requests(
    repo_id: str,
    state: str = "open",
    limit: int = 20,
    store: InMemoryRepositoryStore = Depends(Provide[AppContainer.repository_store]),  # noqa: B008
    repo_provider: Any = Depends(Provide[AppContainer.repo_provider]),  # noqa: B008, ANN401
) -> list[dict[str, Any]]:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo_provider is None:
        raise HTTPException(status_code=503, detail="Repository provider not configured")
    result: list[dict[str, Any]] = await repo_provider.list_pull_requests(repo.url, state, limit)
    return result
