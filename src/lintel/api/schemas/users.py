"""User response models."""

from pydantic import BaseModel


class UserResponse(BaseModel):
    user_id: str
    name: str
    email: str = ""
    role: str = "member"
    slack_user_id: str = ""
    team_ids: list[str] = []
