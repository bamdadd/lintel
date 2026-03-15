"""Code artifact and test result endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.artifacts_api.store import CodeArtifactStore, TestResultStore
from lintel.domain.events import ArtifactStored, TestRunCompleted
from lintel.domain.types import CodeArtifact, TestResult, TestVerdict

router = APIRouter()

code_artifact_store_provider = StoreProvider()
test_result_store_provider = StoreProvider()


# --- Helpers ---


def _test_result_to_dict(result: TestResult) -> dict[str, Any]:
    data = asdict(result)
    data["failures"] = list(result.failures)
    return data


# --- Request models ---


class CreateCodeArtifactRequest(BaseModel):
    artifact_id: str = Field(default_factory=lambda: str(uuid4()))
    work_item_id: str
    run_id: str
    artifact_type: str
    path: str = ""
    content: str = ""
    metadata: dict[str, object] | None = None


class CreateTestResultRequest(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid4()))
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
    request: Request,
    store: CodeArtifactStore = Depends(code_artifact_store_provider),  # noqa: B008
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
    await dispatch_event(
        request,
        ArtifactStored(
            payload={
                "resource_id": body.artifact_id,
                "artifact_type": body.artifact_type,
                "run_id": body.run_id,
            }
        ),
        stream_id=f"artifact:{body.artifact_id}",
    )
    return asdict(artifact)


@router.get("/artifacts")
async def list_artifacts(
    store: CodeArtifactStore = Depends(code_artifact_store_provider),  # noqa: B008
    work_item_id: str | None = None,
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    artifacts = await store.list_all(work_item_id=work_item_id, run_id=run_id)
    return [asdict(a) for a in artifacts]


@router.get("/artifacts/{artifact_id}")
async def get_artifact(
    artifact_id: str,
    store: CodeArtifactStore = Depends(code_artifact_store_provider),  # noqa: B008
) -> dict[str, Any]:
    artifact = await store.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return asdict(artifact)


@router.delete("/artifacts/{artifact_id}", status_code=204)
async def delete_artifact(
    artifact_id: str,
    store: CodeArtifactStore = Depends(code_artifact_store_provider),  # noqa: B008
) -> None:
    artifact = await store.get(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    await store.remove(artifact_id)


# --- Test result endpoints ---


@router.post("/test-results", status_code=201)
async def create_test_result(
    body: CreateTestResultRequest,
    request: Request,
    store: TestResultStore = Depends(test_result_store_provider),  # noqa: B008
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
    await dispatch_event(
        request,
        TestRunCompleted(
            payload={
                "resource_id": body.result_id,
                "run_id": body.run_id,
                "verdict": body.verdict.value,
            }
        ),
        stream_id=f"test_result:{body.result_id}",
    )
    return _test_result_to_dict(result)


@router.get("/test-results")
async def list_test_results(
    store: TestResultStore = Depends(test_result_store_provider),  # noqa: B008
    run_id: str | None = None,
) -> list[dict[str, Any]]:
    results = await store.list_all(run_id=run_id)
    return [_test_result_to_dict(r) for r in results]


@router.get("/test-results/{result_id}")
async def get_test_result(
    result_id: str,
    store: TestResultStore = Depends(test_result_store_provider),  # noqa: B008
) -> dict[str, Any]:
    result = await store.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    return _test_result_to_dict(result)


@router.delete("/test-results/{result_id}", status_code=204)
async def delete_test_result(
    result_id: str,
    store: TestResultStore = Depends(test_result_store_provider),  # noqa: B008
) -> None:
    result = await store.get(result_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Test result not found")
    await store.remove(result_id)
