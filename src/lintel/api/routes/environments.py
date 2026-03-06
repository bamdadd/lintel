"""Environment CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import Environment, EnvironmentType

router = APIRouter()


class InMemoryEnvironmentStore:
    """Simple in-memory store for environments."""

    def __init__(self) -> None:
        self._envs: dict[str, Environment] = {}

    async def add(self, env: Environment) -> None:
        self._envs[env.environment_id] = env

    async def get(self, environment_id: str) -> Environment | None:
        return self._envs.get(environment_id)

    async def list_all(
        self,
        *,
        project_id: str | None = None,
    ) -> list[Environment]:
        envs = list(self._envs.values())
        if project_id is not None:
            envs = [e for e in envs if e.project_id == project_id]
        return envs

    async def update(self, env: Environment) -> None:
        self._envs[env.environment_id] = env

    async def remove(self, environment_id: str) -> None:
        del self._envs[environment_id]


def get_environment_store(request: Request) -> InMemoryEnvironmentStore:
    """Get environment store from app state."""
    return request.app.state.environment_store  # type: ignore[no-any-return]


class CreateEnvironmentRequest(BaseModel):
    environment_id: str
    name: str
    env_type: EnvironmentType = EnvironmentType.DEVELOPMENT
    project_id: str = ""
    config: dict[str, object] | None = None


class UpdateEnvironmentRequest(BaseModel):
    name: str | None = None
    env_type: EnvironmentType | None = None
    project_id: str | None = None
    config: dict[str, object] | None = None


@router.post("/environments", status_code=201)
async def create_environment(
    body: CreateEnvironmentRequest,
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> dict[str, Any]:
    existing = await store.get(body.environment_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Environment already exists")
    env = Environment(
        environment_id=body.environment_id,
        name=body.name,
        env_type=body.env_type,
        project_id=body.project_id,
        config=body.config,
    )
    await store.add(env)
    return asdict(env)


@router.get("/environments")
async def list_environments(
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    envs = await store.list_all(project_id=project_id)
    return [asdict(e) for e in envs]


@router.get("/environments/{environment_id}")
async def get_environment(
    environment_id: str,
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> dict[str, Any]:
    env = await store.get(environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    return asdict(env)


@router.patch("/environments/{environment_id}")
async def update_environment(
    environment_id: str,
    body: UpdateEnvironmentRequest,
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> dict[str, Any]:
    env = await store.get(environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    updates = body.model_dump(exclude_none=True)
    updated = Environment(**{**asdict(env), **updates})
    await store.update(updated)
    return asdict(updated)


@router.delete("/environments/{environment_id}", status_code=204)
async def delete_environment(
    environment_id: str,
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> None:
    env = await store.get(environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    await store.remove(environment_id)
