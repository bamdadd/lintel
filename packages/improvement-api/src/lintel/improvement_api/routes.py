"""Auto-improvement API endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider
from lintel.improvement_api.overfit_guard import check_overfitting
from lintel.improvement_api.store import InMemoryImprovementStore  # noqa: TC001
from lintel.improvement_api.types import (
    FailureDistribution,
    ImprovementDecision,
    ImprovementEntry,
    OverfitCheck,
)
from lintel.workflows.failure_classifier import (
    ClassificationResult,
    FailureClassifier,
)

router = APIRouter()

improvement_store_provider: StoreProvider[InMemoryImprovementStore] = StoreProvider()

_classifier = FailureClassifier()


# --- Request / response models ---


class ClassifyRequest(BaseModel):
    """Request to classify pipeline failures."""

    run_id: str
    failed_stages: list[dict[str, Any]]


class ClassifyResponse(BaseModel):
    """Classified pipeline failure result."""

    run_id: str
    primary_class: str
    failures: list[dict[str, Any]]
    class_distribution: dict[str, int]


class CreateImprovementRequest(BaseModel):
    """Record a new improvement iteration."""

    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    iteration: int = 0
    target_class: str
    description: str = ""
    pass_rate_before: float = 0.0
    pass_rate_after: float = 0.0
    cost_usd: float = 0.0
    decision: ImprovementDecision = ImprovementDecision.PENDING
    overfit_reason: str = ""
    failure_distribution_before: dict[str, int] = {}
    failure_distribution_after: dict[str, int] = {}
    affected_run_ids: list[str] = []


class UpdateImprovementRequest(BaseModel):
    """Update an improvement entry (e.g. after validation)."""

    decision: ImprovementDecision | None = None
    pass_rate_after: float | None = None
    overfit_reason: str | None = None
    failure_distribution_after: dict[str, int] | None = None


class OverfitCheckRequest(BaseModel):
    """Request to validate an improvement against the anti-overfitting rule."""

    target_class: str
    class_pass_rate_before: float
    class_pass_rate_after: float
    affected_runs: int
    overall_pass_rate_before: float
    overall_pass_rate_after: float


class DistributionResponse(BaseModel):
    """Failure distribution summary."""

    total_runs: int
    failed_runs: int
    class_counts: dict[str, int]
    pass_rate: float
    dominant_class: str


# --- Endpoints ---


@router.post("/improvement/classify", tags=["improvement"])
async def classify_failures(body: ClassifyRequest) -> ClassifyResponse:
    """Classify pipeline failures into root cause categories."""
    result: ClassificationResult = _classifier.classify_pipeline(
        body.run_id,
        body.failed_stages,
    )
    return ClassifyResponse(
        run_id=result.run_id,
        primary_class=result.primary_class,
        failures=[
            {
                "failure_class": f.failure_class,
                "stage_name": f.stage_name,
                "matched_pattern": f.matched_pattern,
                "log_snippet": f.log_snippet,
            }
            for f in result.failures
        ],
        class_distribution={k: v for k, v in result.class_distribution.items()},
    )


@router.post("/improvement/overfit-check", tags=["improvement"])
async def validate_overfit(body: OverfitCheckRequest) -> dict[str, Any]:
    """Check whether an improvement change is overfitting."""
    result: OverfitCheck = check_overfitting(
        target_class=body.target_class,
        class_pass_rate_before=body.class_pass_rate_before,
        class_pass_rate_after=body.class_pass_rate_after,
        affected_runs=body.affected_runs,
        overall_pass_rate_before=body.overall_pass_rate_before,
        overall_pass_rate_after=body.overall_pass_rate_after,
    )
    return {
        "passed": result.passed,
        "reason": result.reason,
        "target_class": result.target_class,
        "class_pass_rate_before": result.class_pass_rate_before,
        "class_pass_rate_after": result.class_pass_rate_after,
        "affected_runs": result.affected_runs,
    }


@router.post("/improvement/ledger", status_code=201, tags=["improvement"])
async def create_improvement(
    body: CreateImprovementRequest,
    store: Annotated[InMemoryImprovementStore, Depends(improvement_store_provider)],
) -> dict[str, Any]:
    """Record a new improvement iteration in the ledger."""
    existing = await store.get(body.entry_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Improvement entry already exists")

    entry = ImprovementEntry(
        entry_id=body.entry_id,
        project_id=body.project_id,
        iteration=body.iteration,
        target_class=body.target_class,
        description=body.description,
        pass_rate_before=body.pass_rate_before,
        pass_rate_after=body.pass_rate_after,
        cost_usd=body.cost_usd,
        decision=body.decision,
        overfit_reason=body.overfit_reason,
        failure_distribution_before=body.failure_distribution_before,
        failure_distribution_after=body.failure_distribution_after,
        affected_run_ids=tuple(body.affected_run_ids),
    )
    return await store.add(entry)


@router.get("/improvement/ledger", tags=["improvement"])
async def list_improvements(
    store: Annotated[InMemoryImprovementStore, Depends(improvement_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List improvement ledger entries."""
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/improvement/ledger/{entry_id}", tags=["improvement"])
async def get_improvement(
    entry_id: str,
    store: Annotated[InMemoryImprovementStore, Depends(improvement_store_provider)],
) -> dict[str, Any]:
    """Get a single improvement ledger entry."""
    item = await store.get(entry_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Improvement entry not found")
    return item


@router.patch("/improvement/ledger/{entry_id}", tags=["improvement"])
async def update_improvement(
    entry_id: str,
    body: UpdateImprovementRequest,
    store: Annotated[InMemoryImprovementStore, Depends(improvement_store_provider)],
) -> dict[str, Any]:
    """Update an improvement entry (e.g. decision after validation)."""
    updates = body.model_dump(exclude_none=True)
    result = await store.update(entry_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Improvement entry not found")
    return result


@router.delete("/improvement/ledger/{entry_id}", status_code=204, tags=["improvement"])
async def delete_improvement(
    entry_id: str,
    store: Annotated[InMemoryImprovementStore, Depends(improvement_store_provider)],
) -> None:
    """Remove an improvement ledger entry."""
    if not await store.remove(entry_id):
        raise HTTPException(status_code=404, detail="Improvement entry not found")


@router.get("/improvement/distribution", tags=["improvement"])
async def failure_distribution(
    store: Annotated[InMemoryImprovementStore, Depends(improvement_store_provider)],
    project_id: str | None = None,
) -> DistributionResponse:
    """Get aggregate failure distribution across improvement entries."""
    entries = await store.list_by_project(project_id) if project_id else await store.list_all()
    total = len(entries)
    failed = sum(1 for e in entries if e.get("decision") != ImprovementDecision.KEEP)
    agg: dict[str, int] = {}
    for e in entries:
        for cls, count in e.get("failure_distribution_before", {}).items():
            agg[cls] = agg.get(cls, 0) + count

    dist = FailureDistribution(total_runs=total, failed_runs=failed, class_counts=agg)
    return DistributionResponse(
        total_runs=dist.total_runs,
        failed_runs=dist.failed_runs,
        class_counts=dist.class_counts,
        pass_rate=dist.pass_rate,
        dominant_class=dist.dominant_class,
    )
