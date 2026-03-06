"""Team CRUD endpoints."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import Team

router = APIRouter()


class InMemoryTeamStore:
    """Simple in-memory store for teams."""

    def __init__(self) -> None:
        self._teams: dict[str, Team] = {}

    async def add(self, team: Team) -> None:
        self._teams[team.team_id] = team

    async def get(self, team_id: str) -> Team | None:
        return self._teams.get(team_id)

    async def list_all(self) -> list[Team]:
        return list(self._teams.values())

    async def update(self, team: Team) -> None:
        self._teams[team.team_id] = team

    async def remove(self, team_id: str) -> None:
        del self._teams[team_id]


def get_team_store(request: Request) -> InMemoryTeamStore:
    """Get team store from app state."""
    return request.app.state.team_store  # type: ignore[no-any-return]


class CreateTeamRequest(BaseModel):
    team_id: str
    name: str
    member_ids: list[str] = []
    project_ids: list[str] = []


class UpdateTeamRequest(BaseModel):
    name: str | None = None
    member_ids: list[str] | None = None
    project_ids: list[str] | None = None


def _team_to_dict(team: Team) -> dict[str, Any]:
    data = asdict(team)
    data["member_ids"] = list(team.member_ids)
    data["project_ids"] = list(team.project_ids)
    return data


@router.post("/teams", status_code=201)
async def create_team(
    body: CreateTeamRequest,
    store: Annotated[InMemoryTeamStore, Depends(get_team_store)],
) -> dict[str, Any]:
    existing = await store.get(body.team_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Team already exists")
    team = Team(
        team_id=body.team_id,
        name=body.name,
        member_ids=tuple(body.member_ids),
        project_ids=tuple(body.project_ids),
    )
    await store.add(team)
    return _team_to_dict(team)


@router.get("/teams")
async def list_teams(
    store: Annotated[InMemoryTeamStore, Depends(get_team_store)],
) -> list[dict[str, Any]]:
    teams = await store.list_all()
    return [_team_to_dict(t) for t in teams]


@router.get("/teams/{team_id}")
async def get_team(
    team_id: str,
    store: Annotated[InMemoryTeamStore, Depends(get_team_store)],
) -> dict[str, Any]:
    team = await store.get(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return _team_to_dict(team)


@router.patch("/teams/{team_id}")
async def update_team(
    team_id: str,
    body: UpdateTeamRequest,
    store: Annotated[InMemoryTeamStore, Depends(get_team_store)],
) -> dict[str, Any]:
    team = await store.get(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    updates = body.model_dump(exclude_none=True)
    if "member_ids" in updates:
        updates["member_ids"] = tuple(updates["member_ids"])
    if "project_ids" in updates:
        updates["project_ids"] = tuple(updates["project_ids"])
    updated = Team(**{**asdict(team), **updates})
    await store.update(updated)
    return _team_to_dict(updated)


@router.delete("/teams/{team_id}", status_code=204)
async def delete_team(
    team_id: str,
    store: Annotated[InMemoryTeamStore, Depends(get_team_store)],
) -> None:
    team = await store.get(team_id)
    if team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    await store.remove(team_id)
