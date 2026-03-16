"""In-memory stores for code artifacts and test results."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from lintel.domain.types import CodeArtifact, TestResult


class CodeArtifactStore:
    """In-memory store for code artifacts."""

    def __init__(self) -> None:
        self._artifacts: dict[str, CodeArtifact] = {}

    async def add(self, artifact: CodeArtifact) -> None:
        self._artifacts[artifact.artifact_id] = artifact

    async def get(self, artifact_id: str) -> CodeArtifact | None:
        return self._artifacts.get(artifact_id)

    async def remove(self, artifact_id: str) -> bool:
        return self._artifacts.pop(artifact_id, None) is not None

    async def list_all(
        self,
        *,
        work_item_id: str | None = None,
        run_id: str | None = None,
    ) -> list[CodeArtifact]:
        artifacts = list(self._artifacts.values())
        if work_item_id is not None:
            artifacts = [a for a in artifacts if a.work_item_id == work_item_id]
        if run_id is not None:
            artifacts = [a for a in artifacts if a.run_id == run_id]
        return artifacts


class TestResultStore:
    """In-memory store for test results."""

    def __init__(self) -> None:
        self._results: dict[str, TestResult] = {}

    async def add(self, result: TestResult) -> None:
        self._results[result.result_id] = result

    async def get(self, result_id: str) -> TestResult | None:
        return self._results.get(result_id)

    async def remove(self, result_id: str) -> bool:
        return self._results.pop(result_id, None) is not None

    async def list_all(self, *, run_id: str | None = None) -> list[TestResult]:
        results = list(self._results.values())
        if run_id is not None:
            results = [r for r in results if r.run_id == run_id]
        return results


class ParsedTestResultStore:
    """In-memory store for parsed test results (REQ-010)."""

    def __init__(self) -> None:
        self._results: dict[str, dict[str, Any]] = {}

    async def save(
        self,
        result_id: str,
        run_id: str,
        project_id: str,
        artifact_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "result_id": result_id,
            "run_id": run_id,
            "project_id": project_id,
            "artifact_id": artifact_id,
            **data,
        }
        self._results[result_id] = record
        return record

    async def get_by_run(self, run_id: str) -> list[dict[str, Any]]:
        return [r for r in self._results.values() if r["run_id"] == run_id]

    async def get(self, result_id: str) -> dict[str, Any] | None:
        return self._results.get(result_id)


class CoverageMetricStore:
    """In-memory store for coverage metrics (REQ-010)."""

    def __init__(self) -> None:
        self._metrics: dict[str, dict[str, Any]] = {}

    async def save(
        self,
        metric_id: str,
        run_id: str,
        project_id: str,
        artifact_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        record = {
            "metric_id": metric_id,
            "run_id": run_id,
            "project_id": project_id,
            "artifact_id": artifact_id,
            **data,
        }
        self._metrics[metric_id] = record
        return record

    async def get_by_run(self, run_id: str) -> dict[str, Any] | None:
        for m in self._metrics.values():
            if m["run_id"] == run_id:
                return m
        return None

    async def get_latest_by_project(
        self,
        project_id: str,
    ) -> dict[str, Any] | None:
        matches = [m for m in self._metrics.values() if m["project_id"] == project_id]
        return matches[-1] if matches else None


class QualityGateRuleStore:
    """In-memory store for quality gate rules (REQ-010)."""

    def __init__(self) -> None:
        self._rules: dict[str, dict[str, Any]] = {}

    async def add(self, rule: dict[str, Any]) -> dict[str, Any]:
        self._rules[rule["rule_id"]] = rule
        return rule

    async def get(self, rule_id: str) -> dict[str, Any] | None:
        return self._rules.get(rule_id)

    async def list_by_project(
        self,
        project_id: str,
    ) -> list[dict[str, Any]]:
        return [r for r in self._rules.values() if r["project_id"] == project_id]

    async def update(
        self,
        rule_id: str,
        data: dict[str, Any],
    ) -> dict[str, Any] | None:
        if rule_id not in self._rules:
            return None
        self._rules[rule_id].update(data)
        return self._rules[rule_id]

    async def remove(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None
