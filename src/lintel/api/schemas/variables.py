"""Variable response models."""

from pydantic import BaseModel


class VariableResponse(BaseModel):
    variable_id: str
    key: str
    value: str
    project_id: str = ""
    environment_id: str = ""
    is_secret: bool = False
