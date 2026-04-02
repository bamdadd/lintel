"""Workflow template domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TemplateCategory(StrEnum):
    """Categories of workflow templates."""

    FEATURE = "feature"
    BUGFIX = "bugfix"
    REVIEW = "review"
    DEPLOYMENT = "deployment"
    COMPLIANCE = "compliance"
    CUSTOM = "custom"


@dataclass(frozen=True)
class TemplateParameter:
    """A parameter that can be supplied when instantiating a template."""

    name: str
    type: str  # "str", "int", "bool", "float"
    default_value: Any = None
    required: bool = False
    description: str = ""


@dataclass(frozen=True)
class StageConfig:
    """Configuration for a single stage within a template."""

    name: str
    stage_type: str
    description: str = ""
    timeout_seconds: int = 0
    requires_approval: bool = False


@dataclass(frozen=True)
class WorkflowTemplate:
    """A predefined workflow configuration that users can instantiate."""

    id: str
    name: str
    description: str = ""
    category: TemplateCategory = TemplateCategory.CUSTOM
    stages: tuple[StageConfig, ...] = ()
    default_config: dict[str, Any] = field(default_factory=dict)
    parameters: tuple[TemplateParameter, ...] = ()
    tags: tuple[str, ...] = ()
    version: str = "1.0.0"
