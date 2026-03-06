"""Code artifact and test result endpoints."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import CodeArtifact, TestResult, TestVerdict

router = APIRouter()


# --- Stores ---


class CodeArtifactStore:
    """In-memory store for code artifacts."""

    def __init__(self) -> None:
        self._artifacts: dict[str, CodeArtifact] = {}

    async def add(self, artifact: CodeArtifact) -> None:
        self._artifacts[artifact.artifact_id] = artifact

    async def get(self, artifact_id: str) -> CodeArtifact | None:
        return self._artifacts.get(artifact_id)

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

    async def list_all(self, *, run_id: str | None = None) -> list[TestResult]:
        results = list(self._results.values())
        if run_id is not None:
            results = [r for r in results if r.run_id == run_id]
        return results


def get_code_artifact_store(request: Request) -> CodeArtifactStore:
    """Get code artifact store from app state."""
    return request.app.state.code_artifact_store  # type: ignore[no-any-return]


def get_test_result_store(request: Request) -> TestResultStore:
    """Get test result store from app state."""
    return request.app.state.test_result_store  # type: ignore[no-any-return]


# --- Helpers ---


def _test_result_to_dict(result: TestResult) -> dict[str, Any]:
    data = asdict(result)
    data["failures"] = list(result.failures)
    return data


# --- Request models ---


class CreateCodeArtifactRequest(BaseModel):
    artifact_id: str
    work_item_id: str
    run_id: str
    artifact_type: str
    path: str = ""
    content: str = ""
    metadata: dict[str, object] | None = None


class CreateTestResultRequest(BaseModel):
    result_id: str
    run_id: str
    stage_id: str
    verdict: TestVerdict
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_ms: int = 0
    output: str = ""
    failures: list[str] = []


# --- Artifact endpoints ---


@router.post("/artifacts", status_code=201)
async def create_artifact(
    body: CreateCodeArtifactRequest,
    store: Annotated[CodeArtifactStore, Depends(get_code_artifact_store)],
) -> dict[str, Any]:
    existing = await store.get(body.artifact_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Artifact already exists")
    artifact = CodeArtifact(
        artifact_id=body.artifact_id,
        work_item_id=body.work_item_id,
        run_id=body.run_id,
        artifact_type=body.artifact_type,
        path=body.path,
        content=body.content,
        metadata=body.metadata,
    )
    await store.add(artifact)
    return asdict(artifact)


@router.get("/artifacts")
async def list_artifacts(
    store: Annotated[CodeArtifactStore, Depends(get_code_artifact_store)],
    work_item_id: str | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    artifacts = await store.list_all(work_item_id=work_item_id, run_id=run_id)
    return [asdict(a) for a in artifacts]


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    store: Annotated[CodeArtifactStore, Depends(get_code_artifact_store)],
) -> dict[str, Any]:
    artifact = await store.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return asdict(artifact)


# --- Test result endpoints ---


@router.post("/test-results", status_code=201)
async def create_test_result(
    body: CreateTestResultRequest,
    store: Annotated[TestResultStore, Depends(get_test_result_store)],
) -> dict[str, Any]:
    existing = await store.get(body.result_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Test result already exists")
    result = TestResult(
        result_id=body.result_id,
        run_id=body.run_id,
        stage_id=body.stage_id,
        verdict=body.verdict,
        total=body.total,
        passed=body.passed,
        failed=body.failed,
        errors=body.errors,
        skipped=body.skipped,
        duration_ms=body.duration_ms,
        output=body.output,
        failures=tuple(body.failures),
    )
    await store.add(result)
    return _test_result_to_dict(result)


@router.get("/test-results")
async def list_test_results(
    store: Annotated[TestResultStore, Depends(get_test_result_store)],
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    results = await store.list_all(run_id=run_id)
    return [_test_result_to_dict(r) for r in results]


@router.get("/test-results/{result_id}")
async def get_test_result(
    result_id: str,
    store: Annotated[TestResultStore, Depends(get_test_result_store)],
) -> dict[str, Any]:
    result = await store.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    return _test_result_to_dict(result)
