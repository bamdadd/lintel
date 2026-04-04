"""In-memory store for pipeline diagnostics."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from enum import StrEnum


class FailureCategory(StrEnum):
    agent_error = "agent_error"
    sandbox_timeout = "sandbox_timeout"
    tool_failure = "tool_failure"
    approval_timeout = "approval_timeout"
    infrastructure = "infrastructure"
    unknown = "unknown"


@dataclasses.dataclass
class PipelineDiagnostic:
    diagnostic_id: str = dataclasses.field(
        default_factory=lambda: __import__("uuid").uuid4().hex,
    )
    pipeline_run_id: str = ""
    project_id: str = ""
    work_item_id: str = ""
    failed_stage: str = ""
    error_message: str = ""
    error_traceback: str = ""
    category: str = "unknown"
    context: dict[str, object] = dataclasses.field(default_factory=dict)
    created_at: str = dataclasses.field(
        default_factory=lambda: datetime.now(tz=UTC).isoformat(),
    )


class InMemoryPipelineDiagnosticStore:
    """In-memory store for pipeline diagnostics."""

    def __init__(self) -> None:
        self._diagnostics: dict[str, PipelineDiagnostic] = {}

    async def add(self, diagnostic: PipelineDiagnostic) -> None:
        if diagnostic.diagnostic_id in self._diagnostics:
            msg = f"Diagnostic {diagnostic.diagnostic_id} already exists"
            raise ValueError(msg)
        self._diagnostics[diagnostic.diagnostic_id] = diagnostic

    async def get(self, diagnostic_id: str) -> PipelineDiagnostic | None:
        return self._diagnostics.get(diagnostic_id)

    async def list_all(
        self,
        project_id: str | None = None,
        limit: int = 50,
    ) -> list[PipelineDiagnostic]:
        items = list(self._diagnostics.values())
        if project_id is not None:
            items = [d for d in items if d.project_id == project_id]
        items.sort(key=lambda d: d.created_at, reverse=True)
        return items[:limit]

    async def remove(self, diagnostic_id: str) -> bool:
        return self._diagnostics.pop(diagnostic_id, None) is not None
