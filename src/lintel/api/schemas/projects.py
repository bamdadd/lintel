"""Project response models."""

from pydantic import BaseModel


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    repo_ids: list[str] = []
    default_branch: str = "main"
    credential_ids: list[str] = []
    status: str = "active"
