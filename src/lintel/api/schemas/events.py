"""Event response models."""

from typing import Any

from pydantic import BaseModel


class EventResponse(BaseModel):
    model_config = {"extra": "allow"}


class StreamEventsResponse(BaseModel):
    stream_id: str
    events: list[dict[str, Any]]
    note: str = ""


class CorrelationEventsResponse(BaseModel):
    correlation_id: str
    events: list[dict[str, Any]]
    note: str = ""
