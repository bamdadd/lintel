"""Pydantic request/response models for the chat API."""

from __future__ import annotations

from pydantic import BaseModel


class StartConversationRequest(BaseModel):
    user_id: str
    display_name: str | None = None
    message: str | None = None
    project_id: str | None = None
    model_id: str | None = None


class SendMessageRequest(BaseModel):
    user_id: str
    display_name: str | None = None
    message: str
    role: str = "user"
    model_id: str | None = None
