"""Repository CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.deps import get_repository_store
from lintel.contracts.events import RepositoryRegistered, RepositoryRemoved, RepositoryUpdated
from lintel.contracts.types import Repository, RepoStatus
from lintel.domain.event_dispatcher import dispatch_event
from lintel.infrastructure.repos.repository_store import InMemoryRepositoryStore

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
async def register_repository(
    body: RegisterRepoRequest,
    request: Request,
    store: Annotated[InMemoryRepositoryStore, Depends(get_repository_store)],
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
async def list_repositories(
    store: Annotated[InMemoryRepositoryStore, Depends(get_repository_store)],
) -> list[dict[str, Any]]:
    repos = await store.list_all()
    return [asdict(r) for r in repos]


@router.get("/repositories/{repo_id}")
async def get_repository(
    repo_id: str,
    store: Annotated[InMemoryRepositoryStore, Depends(get_repository_store)],
) -> dict[str, Any]:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    return asdict(repo)


@router.patch("/repositories/{repo_id}")
async def update_repository(
    repo_id: str,
    body: UpdateRepoRequest,
    request: Request,
    store: Annotated[InMemoryRepositoryStore, Depends(get_repository_store)],
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
async def remove_repository(
    repo_id: str,
    request: Request,
    store: Annotated[InMemoryRepositoryStore, Depends(get_repository_store)],
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
