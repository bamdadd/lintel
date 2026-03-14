"""User CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.container import AppContainer
from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.events import UserCreated, UserRemoved, UserUpdated
from lintel.contracts.types import User, UserRole

router = APIRouter()


class InMemoryUserStore:
    """Simple in-memory store for users."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    async def add(self, user: User) -> None:
        self._users[user.user_id] = user

    async def get(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    async def list_all(self) -> list[User]:
        return list(self._users.values())

    async def update(self, user: User) -> None:
        self._users[user.user_id] = user

    async def remove(self, user_id: str) -> None:
        del self._users[user_id]


def get_user_store(request: Request) -> InMemoryUserStore:
    """Kept for backward compat."""
    return request.app.state.user_store  # type: ignore[no-any-return]


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
@inject
async def create_user(
    body: CreateUserRequest,
    request: Request,
    store: InMemoryUserStore = Depends(Provide[AppContainer.user_store]),  # noqa: B008
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
@inject
async def list_users(
    store: InMemoryUserStore = Depends(Provide[AppContainer.user_store]),  # noqa: B008
) -> list[dict[str, Any]]:
    users = await store.list_all()
    return [_user_to_dict(u) for u in users]


@router.get("/users/{user_id}")
@inject
async def get_user(
    user_id: str,
    store: InMemoryUserStore = Depends(Provide[AppContainer.user_store]),  # noqa: B008
) -> dict[str, Any]:
    user = await store.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return _user_to_dict(user)


@router.patch("/users/{user_id}")
@inject
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    store: InMemoryUserStore = Depends(Provide[AppContainer.user_store]),  # noqa: B008
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
@inject
async def delete_user(
    user_id: str,
    request: Request,
    store: InMemoryUserStore = Depends(Provide[AppContainer.user_store]),  # noqa: B008
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
