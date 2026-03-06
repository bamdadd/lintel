"""Repository response models."""

from pydantic import BaseModel


class RepositoryResponse(BaseModel):
    repo_id: str
    name: str
    url: str
    default_branch: str = "main"
    owner: str = ""
    provider: str = "github"
    status: str = "active"
