"""Workspace CRUD endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.multi_tenancy_api.store import InMemoryWorkspaceStore, Workspace

router = APIRouter()

workspace_store_provider: StoreProvider[InMemoryWorkspaceStore] = StoreProvider()


class CreateWorkspaceRequest(BaseModel):
    workspace_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    slug: str
    owner_user_id: str


@router.post("/workspaces", status_code=201)
async def create_workspace(
    body: CreateWorkspaceRequest,
    store: InMemoryWorkspaceStore = Depends(workspace_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.workspace_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Workspace already exists")
    by_slug = await store.get_by_slug(body.slug)
    if by_slug is not None:
        raise HTTPException(status_code=409, detail="Workspace slug already taken")
    workspace = Workspace(
        workspace_id=body.workspace_id,
        name=body.name,
        slug=body.slug,
        owner_user_id=body.owner_user_id,
    )
    await store.add(workspace)
    return asdict(workspace)


@router.get("/workspaces")
async def list_workspaces(
    store: InMemoryWorkspaceStore = Depends(workspace_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    workspaces = await store.list_all()
    return [asdict(w) for w in workspaces]


@router.get("/workspaces/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    store: InMemoryWorkspaceStore = Depends(workspace_store_provider),  # noqa: B008
) -> dict[str, Any]:
    workspace = await store.get(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return asdict(workspace)
