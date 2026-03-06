"""Admin response models."""

from pydantic import BaseModel


class ResetProjectionsResponse(BaseModel):
    status: str
