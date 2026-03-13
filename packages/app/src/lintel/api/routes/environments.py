"""Environment CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from lintel.contracts.events import EnvironmentCreated, EnvironmentRemoved, EnvironmentUpdated
from lintel.contracts.types import Environment, EnvironmentType
from lintel.domain.event_dispatcher import dispatch_event
from pydantic import BaseModel, Field

router = APIRouter()


class InMemoryEnvironmentStore:
    """Simple in-memory store for environments."""

    def __init__(self) -> None:
        self._envs: dict[str, Environment] = {}

    async def add(self, env: Environment) -> None:
        self._envs[env.environment_id] = env

    async def get(self, environment_id: str) -> Environment | None:
        return self._envs.get(environment_id)

    async def list_all(self) -> list[Environment]:
        return list(self._envs.values())

    async def update(self, env: Environment) -> None:
        self._envs[env.environment_id] = env

    async def remove(self, environment_id: str) -> None:
        del self._envs[environment_id]


def get_environment_store(request: Request) -> InMemoryEnvironmentStore:
    """Get environment store from app state."""
    return request.app.state.environment_store  # type: ignore[no-any-return]


class CreateEnvironmentRequest(BaseModel):
    environment_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    env_type: EnvironmentType = EnvironmentType.DEVELOPMENT
    config: dict[str, object] | None = None


class UpdateEnvironmentRequest(BaseModel):
    name: str | None = None
    env_type: EnvironmentType | None = None
    config: dict[str, object] | None = None


@router.post("/environments", status_code=201)
async def create_environment(
    body: CreateEnvironmentRequest,
    request: Request,
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> dict[str, Any]:
    existing = await store.get(body.environment_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Environment already exists")
    env = Environment(
        environment_id=body.environment_id,
        name=body.name,
        env_type=body.env_type,
        config=body.config,
    )
    await store.add(env)
    await dispatch_event(
        request,
        EnvironmentCreated(payload={"resource_id": env.environment_id}),
        stream_id=f"environment:{env.environment_id}",
    )
    return asdict(env)


@router.get("/environments")
async def list_environments(
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> list[dict[str, Any]]:
    envs = await store.list_all()
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
    request: Request,
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> dict[str, Any]:
    env = await store.get(environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    updates = body.model_dump(exclude_none=True)
    updated = Environment(**{**asdict(env), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        EnvironmentUpdated(payload={"resource_id": environment_id}),
        stream_id=f"environment:{environment_id}",
    )
    return asdict(updated)


@router.delete("/environments/{environment_id}", status_code=204)
async def delete_environment(
    environment_id: str,
    request: Request,
    store: Annotated[InMemoryEnvironmentStore, Depends(get_environment_store)],
) -> None:
    env = await store.get(environment_id)
    if env is None:
        raise HTTPException(status_code=404, detail="Environment not found")
    await store.remove(environment_id)
    await dispatch_event(
        request,
        EnvironmentRemoved(payload={"resource_id": environment_id}),
        stream_id=f"environment:{environment_id}",
    )
