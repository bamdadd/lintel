"""User CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import UserCreated, UserRemoved, UserUpdated
from lintel.domain.types import User, UserRole
from lintel.users.store import InMemoryUserStore

router = APIRouter()

user_store_provider: StoreProvider = StoreProvider()


class CreateUserRequest(BaseModel):
    user_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    email: str = ""
    role: UserRole = UserRole.MEMBER
    slack_user_id: str = ""
    team_ids: list[str] = []


class UpdateUserRequest(BaseModel):
    name: str | None = None
    email: str | None = None
    role: UserRole | None = None


def _user_to_dict(user: User) -> dict[str, Any]:
    data = asdict(user)
    data["team_ids"] = list(user.team_ids)
    return data


@router.post("/users", status_code=201)
async def create_user(
    body: CreateUserRequest,
    request: Request,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.user_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists")
    user = User(
        user_id=body.user_id,
        name=body.name,
        email=body.email,
        role=body.role,
        slack_user_id=body.slack_user_id,
        team_ids=tuple(body.team_ids),
    )
    await store.add(user)
    await dispatch_event(
        request,
        UserCreated(payload={"resource_id": body.user_id, "name": body.name}),
        stream_id=f"user:{body.user_id}",
    )
    return _user_to_dict(user)


@router.get("/users")
async def list_users(
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    users = await store.list_all()
    return [_user_to_dict(u) for u in users]


@router.get("/users/{user_id}")
async def get_user(
    user_id: str,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> dict[str, Any]:
    user = await store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> dict[str, Any]:
    user = await store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    updates = body.model_dump(exclude_none=True)
    updated = User(**{**asdict(user), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        UserUpdated(payload={"resource_id": user_id, "fields": list(updates.keys())}),
        stream_id=f"user:{user_id}",
    )
    return _user_to_dict(updated)


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    request: Request,
    store: InMemoryUserStore = Depends(user_store_provider),  # noqa: B008
) -> None:
    user = await store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await store.remove(user_id)
    await dispatch_event(
        request,
        UserRemoved(payload={"resource_id": user_id, "name": user.name}),
        stream_id=f"user:{user_id}",
    )
