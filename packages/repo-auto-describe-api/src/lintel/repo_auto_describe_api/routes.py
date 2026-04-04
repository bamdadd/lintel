"""Repository auto-describe API endpoints."""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.repo_auto_describe_api.store import InMemoryRepoDescriptionStore

router = APIRouter()

repo_description_store_provider: StoreProvider[InMemoryRepoDescriptionStore] = StoreProvider()


@router.post("/repositories/{repo_id}/auto-describe", status_code=201)
async def auto_describe_repository(
    repo_id: str,
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Trigger an analysis of a repository and generate a description.

    In a real implementation this would clone/scan the repo contents.
    For now it simulates discovery of languages, frameworks, and topics.
    """
    from lintel.repo_auto_describe_api.types import RepoDescription

    desc_id = str(uuid4())
    desc = RepoDescription(
        id=desc_id,
        repo_id=repo_id,
        status="running",
        created_at=datetime.now(UTC).isoformat(),
    )
    await store.add(desc)

    # Simulate analysis — a real implementation would inspect repo contents
    completed = RepoDescription(
        id=desc_id,
        repo_id=repo_id,
        summary=f"Auto-generated description for repository {repo_id}",
        languages=("python", "typescript"),
        frameworks=("fastapi", "react"),
        topics=("api", "web"),
        status="completed",
        created_at=desc.created_at,
        completed_at=datetime.now(UTC).isoformat(),
    )
    await store.update(completed)

    return asdict(completed)


@router.get("/repositories/{repo_id}/auto-describe")
async def get_repo_description(
    repo_id: str,
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get the most recent auto-description for a repository."""
    desc = await store.get_by_repo(repo_id)
    if desc is None:
        raise HTTPException(status_code=404, detail="No description found for repository")
    return asdict(desc)


@router.get("/repositories/auto-describe/{description_id}")
async def get_description_by_id(
    description_id: str,
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific auto-description by ID."""
    desc = await store.get(description_id)
    if desc is None:
        raise HTTPException(status_code=404, detail="Description not found")
    return asdict(desc)


@router.get("/repositories/auto-describe")
async def list_descriptions(
    store: InMemoryRepoDescriptionStore = Depends(repo_description_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all auto-descriptions."""
    descriptions = await store.list_all()
    return [asdict(d) for d in descriptions]
