"""Code artifact and test result endpoints."""

import asyncio
import base64
from collections.abc import AsyncGenerator
from dataclasses import asdict
import json
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.artifacts_api.store import (
    CodeArtifactStore,
    CoverageMetricStore,
    ParsedTestResultStore,
    QualityGateRuleStore,
    TestResultStore,
)
from lintel.contracts.protocols.artifact_store import ArtifactStore
from lintel.domain.events import (
    ArtifactStored,
    CoverageMeasured,
    TestResultsParsed,
    TestRunCompleted,
)
from lintel.domain.types import CodeArtifact, TestResult, TestVerdict

router = APIRouter()

code_artifact_store_provider: StoreProvider[CodeArtifactStore] = StoreProvider()
test_result_store_provider: StoreProvider[TestResultStore] = StoreProvider()
pipeline_store_provider: StoreProvider[object] = StoreProvider()
artifact_content_store_provider: StoreProvider[ArtifactStore] = StoreProvider()
parsed_result_store_provider: StoreProvider[ParsedTestResultStore] = StoreProvider()
coverage_metric_store_provider: StoreProvider[CoverageMetricStore] = StoreProvider()
quality_gate_rule_store_provider: StoreProvider[QualityGateRuleStore] = StoreProvider()


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


@router.get("/artifacts/stream")
async def stream_artifacts(
    run_id: str,
    artifact_store: CodeArtifactStore = Depends(code_artifact_store_provider),  # noqa: B008
    test_store: TestResultStore = Depends(test_result_store_provider),  # noqa: B008
    pipe_store: object = Depends(pipeline_store_provider),
) -> StreamingResponse:
    """Stream artifacts and test results for a running pipeline via SSE.

    Emits ``artifact`` events as new code artifacts appear and ``test_result``
    events for new test results.  The stream ends with a ``complete`` event once
    the pipeline reaches a terminal state (succeeded / failed / cancelled) or is
    not found.
    """

    async def event_stream() -> AsyncGenerator[str, None]:
        seen_artifacts: set[str] = set()
        seen_results: set[str] = set()

        while True:
            # Check pipeline status
            run = await pipe_store.get(run_id) if pipe_store else None
            terminal = False
            if run is not None:
                status = run.status.value if hasattr(run.status, "value") else str(run.status)
                terminal = status in ("succeeded", "failed", "cancelled")

            # Emit new artifacts
            artifacts = await artifact_store.list_all(run_id=run_id)
            for a in artifacts:
                if a.artifact_id not in seen_artifacts:
                    seen_artifacts.add(a.artifact_id)
                    payload = {"type": "artifact", "data": asdict(a)}
                    yield f"data: {json.dumps(payload, default=str)}\n\n"

            # Emit new test results
            results = await test_store.list_all(run_id=run_id)
            for r in results:
                if r.result_id not in seen_results:
                    seen_results.add(r.result_id)
                    payload = {"type": "test_result", "data": _test_result_to_dict(r)}
                    yield f"data: {json.dumps(payload, default=str)}\n\n"

            if terminal or run is None:
                yield f"data: {json.dumps({'type': 'complete'})}\n\n"
                return

            await asyncio.sleep(1)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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


# --- Request models (REQ-010) ---


class UploadArtifactRequest(BaseModel):
    run_id: str
    project_id: str
    artifact_type: str  # test_result or coverage
    mime_type: str | None = None
    extension: str | None = None
    content_base64: str  # base64-encoded artifact content


class CreateQualityGateRuleRequest(BaseModel):
    rule_id: str = Field(default_factory=lambda: str(uuid4()))
    rule_type: str  # min_pass_rate, min_coverage, max_coverage_drop
    threshold: float
    severity: str = "error"
    enabled: bool = True


# --- Parsed test results endpoints (REQ-010) ---


@router.post("/artifacts/upload", status_code=201)
async def upload_artifact(
    body: UploadArtifactRequest,
    request: Request,
    parsed_store: ParsedTestResultStore = Depends(  # noqa: B008
        parsed_result_store_provider,
    ),
    coverage_store: CoverageMetricStore = Depends(  # noqa: B008
        coverage_metric_store_provider,
    ),
) -> dict[str, Any]:
    """Upload and parse a test result or coverage artifact."""
    from lintel.domain.artifacts.parsers.registry import ParserRegistry

    raw_bytes = base64.b64decode(body.content_base64)
    registry = ParserRegistry()
    artifact_id = str(uuid4())
    result: dict[str, Any] = {"artifact_id": artifact_id}

    if body.artifact_type == "test_result":
        parser = registry.get_artifact_parser(
            mime_type=body.mime_type,
            extension=body.extension,
        )
        parsed = parser.parse(raw_bytes)

        record = await parsed_store.save(
            result_id=str(uuid4()),
            run_id=body.run_id,
            project_id=body.project_id,
            artifact_id=artifact_id,
            data=asdict(parsed),
        )
        result["parsed"] = record
        await dispatch_event(
            request,
            TestResultsParsed(
                payload={
                    "run_id": body.run_id,
                    "project_id": body.project_id,
                    "artifact_id": artifact_id,
                    "total": parsed.total,
                    "passed": parsed.passed,
                    "failed": parsed.failed,
                    "pass_rate": parsed.pass_rate,
                }
            ),
            stream_id=f"artifact:{artifact_id}",
        )
    elif body.artifact_type == "coverage":
        parser = registry.get_coverage_parser(
            mime_type=body.mime_type,
            extension=body.extension,
        )
        report = parser.parse(raw_bytes)

        record = await coverage_store.save(
            metric_id=str(uuid4()),
            run_id=body.run_id,
            project_id=body.project_id,
            artifact_id=artifact_id,
            data=asdict(report),
        )
        result["coverage"] = record
        await dispatch_event(
            request,
            CoverageMeasured(
                payload={
                    "run_id": body.run_id,
                    "project_id": body.project_id,
                    "artifact_id": artifact_id,
                    "line_rate": report.line_rate,
                    "branch_rate": report.branch_rate,
                }
            ),
            stream_id=f"artifact:{artifact_id}",
        )
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown artifact_type: {body.artifact_type}",
        )

    return result


@router.get("/artifacts/test-results/{run_id}")
async def get_parsed_test_results(
    run_id: str,
    store: ParsedTestResultStore = Depends(  # noqa: B008
        parsed_result_store_provider,
    ),
) -> list[dict[str, Any]]:
    """Get parsed test result summary for a run."""
    return await store.get_by_run(run_id)


@router.get("/artifacts/coverage/{run_id}")
async def get_coverage_metrics(
    run_id: str,
    store: CoverageMetricStore = Depends(  # noqa: B008
        coverage_metric_store_provider,
    ),
) -> dict[str, Any]:
    """Get coverage metrics for a run."""
    result = await store.get_by_run(run_id)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Coverage not found for run",
        )
    return result


# --- Quality gate rule endpoints (REQ-010) ---


@router.get("/projects/{project_id}/quality-gate-rules")
async def list_quality_gate_rules(
    project_id: str,
    store: QualityGateRuleStore = Depends(  # noqa: B008
        quality_gate_rule_store_provider,
    ),
) -> list[dict[str, Any]]:
    return await store.list_by_project(project_id)


@router.post(
    "/projects/{project_id}/quality-gate-rules",
    status_code=201,
)
async def create_quality_gate_rule(
    project_id: str,
    body: CreateQualityGateRuleRequest,
    store: QualityGateRuleStore = Depends(  # noqa: B008
        quality_gate_rule_store_provider,
    ),
) -> dict[str, Any]:
    rule = {
        "rule_id": body.rule_id,
        "project_id": project_id,
        "rule_type": body.rule_type,
        "threshold": body.threshold,
        "severity": body.severity,
        "enabled": body.enabled,
    }
    return await store.add(rule)


@router.delete(
    "/projects/{project_id}/quality-gate-rules/{rule_id}",
    status_code=204,
)
async def delete_quality_gate_rule(
    project_id: str,
    rule_id: str,
    store: QualityGateRuleStore = Depends(  # noqa: B008
        quality_gate_rule_store_provider,
    ),
) -> None:
    existing = await store.get(rule_id)
    if existing is None:
        raise HTTPException(
            status_code=404,
            detail="Quality gate rule not found",
        )
    await store.remove(rule_id)
