"""Repository CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.repos.classifier import RepoClassifier
from lintel.repos.events import (
    RepositoryCreated,
    RepositoryRegistered,
    RepositoryRemoved,
    RepositoryUpdated,
)
from lintel.repos.repository_store import InMemoryRepositoryStore
from lintel.repos.templates import list_templates
from lintel.repos.types import Repository, RepoStatus, RepoTemplate

router = APIRouter()

repository_store_provider: StoreProvider = StoreProvider()
repo_provider_provider: StoreProvider = StoreProvider()

_repo_classifier = RepoClassifier()


def _gen_id() -> str:
    return str(uuid4())


class RegisterRepoRequest(BaseModel):
    repo_id: str = Field(default_factory=_gen_id)
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    project_ids: list[str] = []


class CreateRepoRequest(BaseModel):
    """Request to create a new GitHub repo from a scaffold template."""

    name: str
    owner: str
    template: RepoTemplate | None = None
    private: bool = True
    description: str = ""
    project_ids: list[str] = []


class UpdateRepoRequest(BaseModel):
    name: str | None = None
    default_branch: str | None = None
    owner: str | None = None
    status: RepoStatus | None = None
    project_ids: list[str] | None = None


@router.post("/repositories", status_code=201)
async def register_repository(
    body: RegisterRepoRequest,
    request: Request,
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
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
        project_ids=tuple(body.project_ids),
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
    project_id: str | None = None,
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    repos = await store.list_all()
    if project_id is not None:
        repos = [r for r in repos if project_id in r.project_ids]
    return [asdict(r) for r in repos]


@router.get("/repositories/templates")
async def list_repository_templates() -> dict[str, Any]:
    """List available scaffold templates for new repositories."""
    return {"templates": list_templates()}


@router.post("/repositories/create", status_code=201)
async def create_repository(
    body: CreateRepoRequest,
    request: Request,
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
    repo_provider: Any = Depends(repo_provider_provider),  # noqa: B008, ANN401
) -> dict[str, Any]:
    """Create a new GitHub repository from a scaffold template and register it."""
    if repo_provider is None:
        raise HTTPException(status_code=503, detail="Repository provider not configured")

    result = await repo_provider.create_repo(
        body.owner,
        body.name,
        private=body.private,
        description=body.description,
        template=body.template,
    )

    repo_id = _gen_id()
    repo = Repository(
        repo_id=repo_id,
        name=result.name,
        url=result.repo_url,
        default_branch=result.default_branch,
        owner=result.owner,
        provider="github",
        project_ids=tuple(body.project_ids),
    )
    await store.add(repo)

    await dispatch_event(
        request,
        RepositoryCreated(
            payload={
                "resource_id": repo_id,
                "name": result.name,
                "url": result.repo_url,
                "template": body.template.value if body.template else None,
            }
        ),
        stream_id=f"repository:{repo_id}",
    )
    return asdict(repo)


class ClassifyRequest(BaseModel):
    message: str
    top_k: int = Field(default=3, ge=1, le=20)


@router.post("/repositories/classify")
async def classify_repository(
    body: ClassifyRequest,
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Classify which repository a user message relates to."""
    repos = await store.list_all()
    active_repos = [r for r in repos if r.status == RepoStatus.ACTIVE]
    classifications = _repo_classifier.classify(body.message, active_repos)
    top = classifications[: body.top_k]
    return {
        "message": body.message,
        "results": [
            {
                "repo_id": c.repo_id,
                "repo_name": c.repo_name,
                "confidence": round(c.confidence, 4),
                "matched_keywords": list(c.matched_keywords),
                "reason": c.reason,
            }
            for c in top
        ],
        "needs_clarification": len(top) == 0 or (len(top) > 0 and top[0].confidence < 0.4),
    }


@router.get("/repositories/{repo_id}")
async def get_repository(
    repo_id: str,
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
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
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
) -> dict[str, Any]:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    updates = body.model_dump(exclude_none=True)
    if "project_ids" in updates:
        updates["project_ids"] = tuple(updates["project_ids"])
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
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
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
async def list_repository_commits(
    repo_id: str,
    branch: str | None = None,
    limit: int = 20,
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
    repo_provider: Any = Depends(repo_provider_provider),  # noqa: B008, ANN401
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
async def list_repository_pull_requests(
    repo_id: str,
    state: str = "open",
    limit: int = 20,
    store: InMemoryRepositoryStore = Depends(repository_store_provider),  # noqa: B008
    repo_provider: Any = Depends(repo_provider_provider),  # noqa: B008, ANN401
) -> list[dict[str, Any]]:
    repo = await store.get(repo_id)
    if repo is None:
        raise HTTPException(status_code=404, detail="Repository not found")
    if repo_provider is None:
        raise HTTPException(status_code=503, detail="Repository provider not configured")
    result: list[dict[str, Any]] = await repo_provider.list_pull_requests(repo.url, state, limit)
    return result
