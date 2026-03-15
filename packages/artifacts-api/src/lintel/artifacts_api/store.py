"""In-memory stores for code artifacts and test results."""

from __future__ import annotations

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
