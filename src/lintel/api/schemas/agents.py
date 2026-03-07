"""Agent response models."""

from typing import Any

from pydantic import BaseModel


class TestPromptResponse(BaseModel):
    agent_role: str
    messages: list[dict[str, str]]
    response: dict[str, Any]


class AgentStepCommandResponse(BaseModel):
    model_config = {"extra": "allow"}

    thread_ref: dict[str, str] = {}
    agent_role: str = ""
    step_name: str = ""


class AgentDefinitionResponse(BaseModel):
    agent_id: str
    name: str
    description: str = ""
    system_prompt: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0
    allowed_skills: list[str] = []
    role: str = ""
