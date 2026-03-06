"""Metrics response models."""

from typing import Any

from pydantic import BaseModel


class PiiStatsResponse(BaseModel):
    total_scanned: int = 0
    total_detected: int = 0
    total_anonymised: int = 0
    total_blocked: int = 0
    total_reveals: int = 0


class PiiMetricsResponse(BaseModel):
    pii: PiiStatsResponse


class AgentMetricsResponse(BaseModel):
    total_steps: int
    activity: list[dict[str, Any]]


class SandboxOverview(BaseModel):
    total: int


class ConnectionOverview(BaseModel):
    total: int


class OverviewMetricsResponse(BaseModel):
    pii: PiiStatsResponse
    sandboxes: SandboxOverview
    connections: ConnectionOverview
