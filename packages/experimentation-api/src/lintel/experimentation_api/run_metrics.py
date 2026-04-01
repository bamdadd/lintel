"""Run-level metrics capture, strategy mutations, and tournament selection."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import (
    RunMetricRecorded,
    StrategyMutationSuggested,
    TournamentCompleted,
)
from lintel.domain.types import (
    MutationStrategy,
    RunMetric,
    StrategyMutation,
    TournamentResult,
)

router = APIRouter()

run_metric_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
mutation_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
tournament_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


# --- Run Metrics ---


class CreateRunMetricRequest(BaseModel):
    run_metric_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    experiment_id: str = ""
    metric_name: str = ""
    value: float = 0.0
    unit: str = ""
    timestamp: str = ""
    tags: list[str] = []


class BatchRunMetricsRequest(BaseModel):
    metrics: list[CreateRunMetricRequest]


@router.post("/run-metrics", status_code=201)
async def create_run_metric(
    request: Request,
    body: CreateRunMetricRequest,
    store: Annotated[ComplianceStore, Depends(run_metric_store_provider)],
) -> dict[str, Any]:
    metric = RunMetric(
        run_metric_id=body.run_metric_id,
        run_id=body.run_id,
        experiment_id=body.experiment_id,
        metric_name=body.metric_name,
        value=body.value,
        unit=body.unit,
        timestamp=body.timestamp,
        tags=tuple(body.tags),
    )
    result = await store.add(metric)
    await dispatch_event(
        request,
        RunMetricRecorded(payload={"resource_id": body.run_metric_id, "run_id": body.run_id}),
        stream_id=f"run_metric:{body.run_metric_id}",
    )
    return result


@router.post("/run-metrics/batch", status_code=201)
async def batch_create_run_metrics(
    request: Request,
    body: BatchRunMetricsRequest,
    store: Annotated[ComplianceStore, Depends(run_metric_store_provider)],
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in body.metrics:
        metric = RunMetric(
            run_metric_id=item.run_metric_id,
            run_id=item.run_id,
            experiment_id=item.experiment_id,
            metric_name=item.metric_name,
            value=item.value,
            unit=item.unit,
            timestamp=item.timestamp,
            tags=tuple(item.tags),
        )
        result = await store.add(metric)
        results.append(result)
    return results


@router.get("/run-metrics")
async def list_run_metrics(
    store: Annotated[ComplianceStore, Depends(run_metric_store_provider)],
    run_id: str | None = None,
    experiment_id: str | None = None,
) -> list[dict[str, Any]]:
    all_items = await store.list_all()
    if run_id:
        all_items = [m for m in all_items if m.get("run_id") == run_id]
    if experiment_id:
        all_items = [m for m in all_items if m.get("experiment_id") == experiment_id]
    return all_items


@router.get("/run-metrics/{run_metric_id}")
async def get_run_metric(
    run_metric_id: str,
    store: Annotated[ComplianceStore, Depends(run_metric_store_provider)],
) -> dict[str, Any]:
    item = await store.get(run_metric_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Run metric not found")
    return item


@router.delete("/run-metrics/{run_metric_id}", status_code=204)
async def remove_run_metric(
    run_metric_id: str,
    store: Annotated[ComplianceStore, Depends(run_metric_store_provider)],
) -> None:
    if not await store.remove(run_metric_id):
        raise HTTPException(status_code=404, detail="Run metric not found")


# --- Strategy Mutations ---


class CreateMutationRequest(BaseModel):
    mutation_id: str = Field(default_factory=lambda: str(uuid4()))
    experiment_id: str
    source_run_id: str
    strategy: MutationStrategy = MutationStrategy.CUSTOM
    description: str = ""
    config_patch: dict[str, object] | None = None
    applied: bool = False
    created_at: str = ""


@router.post("/strategy-mutations", status_code=201)
async def create_strategy_mutation(
    request: Request,
    body: CreateMutationRequest,
    store: Annotated[ComplianceStore, Depends(mutation_store_provider)],
) -> dict[str, Any]:
    mutation = StrategyMutation(
        mutation_id=body.mutation_id,
        experiment_id=body.experiment_id,
        source_run_id=body.source_run_id,
        strategy=body.strategy,
        description=body.description,
        config_patch=body.config_patch,
        applied=body.applied,
        created_at=body.created_at,
    )
    result = await store.add(mutation)
    await dispatch_event(
        request,
        StrategyMutationSuggested(
            payload={"resource_id": body.mutation_id, "experiment_id": body.experiment_id}
        ),
        stream_id=f"mutation:{body.mutation_id}",
    )
    return result


@router.get("/strategy-mutations")
async def list_strategy_mutations(
    store: Annotated[ComplianceStore, Depends(mutation_store_provider)],
    experiment_id: str | None = None,
) -> list[dict[str, Any]]:
    all_items = await store.list_all()
    if experiment_id:
        all_items = [m for m in all_items if m.get("experiment_id") == experiment_id]
    return all_items


@router.get("/strategy-mutations/{mutation_id}")
async def get_strategy_mutation(
    mutation_id: str,
    store: Annotated[ComplianceStore, Depends(mutation_store_provider)],
) -> dict[str, Any]:
    item = await store.get(mutation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy mutation not found")
    return item


@router.patch("/strategy-mutations/{mutation_id}")
async def update_strategy_mutation(
    mutation_id: str,
    body: dict[str, Any],
    store: Annotated[ComplianceStore, Depends(mutation_store_provider)],
) -> dict[str, Any]:
    result = await store.update(mutation_id, body)
    if result is None:
        raise HTTPException(status_code=404, detail="Strategy mutation not found")
    return result


# --- Tournament Selection ---


class RunTournamentRequest(BaseModel):
    """Request to run a tournament comparing metrics across runs."""

    tournament_id: str = Field(default_factory=lambda: str(uuid4()))
    experiment_id: str
    task_key: str = ""
    run_ids: list[str] = []
    metric_name: str = ""
    direction: str = "maximize"  # "maximize" or "minimize"


@router.post("/tournaments", status_code=201)
async def run_tournament(
    request: Request,
    body: RunTournamentRequest,
    metric_store: Annotated[ComplianceStore, Depends(run_metric_store_provider)],
    tournament_store: Annotated[ComplianceStore, Depends(tournament_store_provider)],
) -> dict[str, Any]:
    """Compare run metrics and select the best-performing run."""
    all_metrics = await metric_store.list_all()

    # Collect scores: best metric value per run for the given metric_name
    scores: dict[str, float] = {}
    for m in all_metrics:
        if m.get("run_id") in body.run_ids and m.get("metric_name") == body.metric_name:
            rid = m["run_id"]
            val = float(m.get("value", 0))
            # Keep best value per run (last recorded wins for ties)
            scores[rid] = val

    # Determine winner
    winning_run_id = ""
    if scores:
        if body.direction == "minimize":
            winning_run_id = min(scores, key=lambda k: scores[k])
        else:
            winning_run_id = max(scores, key=lambda k: scores[k])

    result_obj = TournamentResult(
        tournament_id=body.tournament_id,
        experiment_id=body.experiment_id,
        task_key=body.task_key,
        run_ids=tuple(body.run_ids),
        winning_run_id=winning_run_id,
        metric_name=body.metric_name,
        scores=scores,
        selected_at="",
    )
    result = await tournament_store.add(result_obj)
    await dispatch_event(
        request,
        TournamentCompleted(
            payload={
                "resource_id": body.tournament_id,
                "winning_run_id": winning_run_id,
            }
        ),
        stream_id=f"tournament:{body.tournament_id}",
    )
    return result


@router.get("/tournaments")
async def list_tournaments(
    store: Annotated[ComplianceStore, Depends(tournament_store_provider)],
    experiment_id: str | None = None,
) -> list[dict[str, Any]]:
    all_items = await store.list_all()
    if experiment_id:
        all_items = [t for t in all_items if t.get("experiment_id") == experiment_id]
    return all_items


@router.get("/tournaments/{tournament_id}")
async def get_tournament(
    tournament_id: str,
    store: Annotated[ComplianceStore, Depends(tournament_store_provider)],
) -> dict[str, Any]:
    item = await store.get(tournament_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Tournament not found")
    return item


def suggest_mutations_for_failure(
    run_id: str,
    experiment_id: str,
    failure_reason: str = "",
) -> list[StrategyMutation]:
    """Generate mutated config suggestions based on a failed run.

    This is a pure function that returns mutation suggestions.
    The caller is responsible for persisting them via the API.
    """
    suggestions: list[StrategyMutation] = []

    if "timeout" in failure_reason.lower():
        suggestions.append(
            StrategyMutation(
                mutation_id=str(uuid4()),
                experiment_id=experiment_id,
                source_run_id=run_id,
                strategy=MutationStrategy.INCREASE_TIMEOUT,
                description="Increase timeout to handle slow operations",
                config_patch={"timeout_multiplier": 2.0},
            )
        )

    if "concurren" in failure_reason.lower() or "resource" in failure_reason.lower():
        suggestions.append(
            StrategyMutation(
                mutation_id=str(uuid4()),
                experiment_id=experiment_id,
                source_run_id=run_id,
                strategy=MutationStrategy.REDUCE_CONCURRENCY,
                description="Reduce concurrency to avoid resource contention",
                config_patch={"max_concurrent": 1},
            )
        )

    if "model" in failure_reason.lower() or "llm" in failure_reason.lower():
        suggestions.append(
            StrategyMutation(
                mutation_id=str(uuid4()),
                experiment_id=experiment_id,
                source_run_id=run_id,
                strategy=MutationStrategy.SWITCH_MODEL,
                description="Switch to a different model provider",
                config_patch={"model_fallback": True},
            )
        )

    # Always suggest retry as a fallback
    if not suggestions:
        suggestions.append(
            StrategyMutation(
                mutation_id=str(uuid4()),
                experiment_id=experiment_id,
                source_run_id=run_id,
                strategy=MutationStrategy.ADD_RETRY,
                description="Add retry with backoff",
                config_patch={"max_retries": 3, "backoff_factor": 2.0},
            )
        )

    return suggestions
