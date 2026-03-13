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


# --- MET-5: Quality Metrics ---


class CoverageDeltaEntry(BaseModel):
    project_id: str
    commit_sha: str
    pr_id: str
    coverage_before: float
    coverage_after: float
    delta: float
    occurred_at: str


class DefectDensityResponse(BaseModel):
    bug_count: int
    lines_changed: int
    density: float
    window_days: int


class ReworkRatioResponse(BaseModel):
    rework_loc: int
    total_loc: int
    ratio: float
    window_days: int


class QualityMetricsResponse(BaseModel):
    coverage_deltas: list[CoverageDeltaEntry]
    defect_density: DefectDensityResponse
    rework_ratio: ReworkRatioResponse
    window_days: int
