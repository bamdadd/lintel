"""Team response models."""

from pydantic import BaseModel


class TeamResponse(BaseModel):
    team_id: str
    name: str
    member_ids: list[str] = []
    project_ids: list[str] = []
