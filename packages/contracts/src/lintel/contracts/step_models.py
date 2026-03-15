"""Step model override contracts for per-step model assignment (REQ-021)."""

from __future__ import annotations

from datetime import datetime  # noqa: TC003
from enum import StrEnum
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel


class NodeType(StrEnum):
    """Known workflow node types for per-step model assignment."""

    RESEARCH = "research"
    PLAN = "plan"
    IMPLEMENT = "implement"
    REVIEW = "review"
    TEST = "test"
    TRIAGE = "triage"
    ANALYSE = "analyse"
    SETUP_WORKSPACE = "setup_workspace"
    CLOSE = "close"
    INGEST = "ingest"
    ROUTE = "route"


class ProjectStepModelOverride(BaseModel, frozen=True):
    """Per-step model override for a project."""

    project_id: UUID
    node_type: NodeType
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime


class StepModelOverrideRequest(BaseModel, frozen=True):
    """Request body for creating/updating a step model override."""

    provider: str
    model: str


class StepModelOverrideResponse(BaseModel, frozen=True):
    """Response body for a step model override."""

    project_id: UUID
    node_type: NodeType
    provider: str
    model: str
    created_at: datetime
    updated_at: datetime
