"""Project response models."""

from pydantic import BaseModel


class ProjectResponse(BaseModel):
    project_id: str
    name: str
    repo_id: str = ""
    channel_id: str = ""
    workspace_id: str = ""
    workflow_definition_id: str = "feature_to_pr"
    default_branch: str = "main"
    credential_ids: list[str] = []
    ai_provider_id: str = ""
    status: str = "active"
