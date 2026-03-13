"""Skill response models."""

from typing import Any

from pydantic import BaseModel


class SkillResponse(BaseModel):
    skill_id: str
    name: str = ""
    version: str = ""
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    execution_mode: str = "inline"


class SkillInvocationResponse(BaseModel):
    success: bool
    output: dict[str, Any] = {}
