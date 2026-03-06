"""Workflow response models."""


from pydantic import BaseModel


class WorkflowCommandResponse(BaseModel):
    model_config = {"extra": "allow"}

    thread_ref: dict[str, str] = {}
    workflow_type: str = ""


class WorkflowStatusResponse(BaseModel):
    model_config = {"extra": "allow"}

    stream_id: str = ""
    phase: str = ""
    status: str = ""
