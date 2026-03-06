"""Thread response models."""

from pydantic import BaseModel


class ThreadStatusResponse(BaseModel):
    model_config = {"extra": "allow"}

    stream_id: str = ""
    workspace_id: str = ""
    channel_id: str = ""
    thread_ts: str = ""
    phase: str = ""
    status: str = ""
