"""Artifact and test result response models."""

from typing import Any

from pydantic import BaseModel


class CodeArtifactResponse(BaseModel):
    artifact_id: str
    work_item_id: str
    run_id: str
    artifact_type: str
    path: str = ""
    content: str = ""
    metadata: dict[str, Any] | None = None


class TestResultResponse(BaseModel):
    result_id: str
    run_id: str
    stage_id: str
    verdict: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int = 0
    output: str = ""
    failures: list[str] = []
