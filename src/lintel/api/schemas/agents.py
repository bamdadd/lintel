"""Agent response models."""

from typing import Any

from pydantic import BaseModel


class ModelPolicyResponse(BaseModel):
    role: str = ""
    provider: str = ""
    model_name: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0


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
    model_policy: dict[str, Any] = {}
    allowed_skills: list[str] = []
    role: str = ""
