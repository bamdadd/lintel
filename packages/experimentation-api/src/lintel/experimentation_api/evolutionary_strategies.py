"""Evolutionary strategy CRUD + mutation endpoints (REQ-034.2.2/034.2.3)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    EvolutionaryStrategyCreated,
    EvolutionaryStrategyRemoved,
    EvolutionaryStrategyUpdated,
)
from lintel.domain.evolutionary_strategy import (
    EvolutionaryStrategy,
    FailedRunContext,
)
from lintel.domain.strategy_mutation import mutate_strategy

router = APIRouter()

evo_strategy_store_provider: StoreProvider[Any] = StoreProvider()


class CreateEvolutionaryStrategyRequest(BaseModel):
    strategy_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    config: dict[str, Any] = {}
    parent_strategy_id: str = ""
    generation: int = 0


class UpdateEvolutionaryStrategyRequest(BaseModel):
    status: str | None = None
    score: float | None = None


class MutateStrategyRequest(BaseModel):
    run_id: str = ""
    failure_reason: str = ""
    metrics: list[dict[str, Any]] = []


@router.post("/strategies/evolutionary", status_code=201)
async def create_evolutionary_strategy(
    request: Request,
    body: CreateEvolutionaryStrategyRequest,
    store: Any = Depends(evo_strategy_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Create a new evolutionary strategy."""
    existing = await store.get(body.strategy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Strategy already exists")
    strategy = EvolutionaryStrategy(
        strategy_id=body.strategy_id,
        name=body.name,
        config=body.config,
        parent_strategy_id=body.parent_strategy_id,
        generation=body.generation,
    )
    result = await store.add(strategy)
    await dispatch_event(
        request,
        EvolutionaryStrategyCreated(
            payload={"resource_id": body.strategy_id, "name": body.name},
        ),
        stream_id=f"evo_strategy:{body.strategy_id}",
    )
    return result


@router.get("/strategies/evolutionary")
async def list_evolutionary_strategies(
    store: Any = Depends(evo_strategy_store_provider),  # noqa: ANN401, B008
    status: str | None = None,
) -> list[dict[str, Any]]:
    """List evolutionary strategies, optionally filtered by status."""
    items = await store.list_all()
    if status:
        items = [i for i in items if i.get("status") == status]
    return items


@router.get("/strategies/evolutionary/{strategy_id}")
async def get_evolutionary_strategy(
    strategy_id: str,
    store: Any = Depends(evo_strategy_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Get a single evolutionary strategy."""
    item = await store.get(strategy_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return item


@router.get("/strategies/evolutionary/{strategy_id}/lineage")
async def get_strategy_lineage(
    strategy_id: str,
    store: Any = Depends(evo_strategy_store_provider),  # noqa: ANN401, B008
) -> list[dict[str, Any]]:
    """Get the full lineage tree for a strategy (root to leaf)."""
    lineage: list[dict[str, Any]] = []
    current_id = strategy_id
    visited: set[str] = set()

    while current_id and current_id not in visited:
        visited.add(current_id)
        item = await store.get(current_id)
        if item is None:
            break
        lineage.append(item)
        current_id = item.get("parent_strategy_id", "")

    lineage.reverse()
    return lineage


@router.patch("/strategies/evolutionary/{strategy_id}")
async def update_evolutionary_strategy(
    request: Request,
    strategy_id: str,
    body: UpdateEvolutionaryStrategyRequest,
    store: Any = Depends(evo_strategy_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Update score and/or status of a strategy."""
    updates = body.model_dump(exclude_none=True)
    result = await store.update(strategy_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    await dispatch_event(
        request,
        EvolutionaryStrategyUpdated(payload={"resource_id": strategy_id}),
        stream_id=f"evo_strategy:{strategy_id}",
    )
    return result


@router.post("/strategies/evolutionary/{strategy_id}/mutate")
async def mutate_evolutionary_strategy(
    strategy_id: str,
    body: MutateStrategyRequest,
    store: Any = Depends(evo_strategy_store_provider),  # noqa: ANN401, B008
) -> dict[str, Any]:
    """Trigger a mutation on a strategy, returning a StrategyMutationProposal."""
    item = await store.get(strategy_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy not found")

    strategy = EvolutionaryStrategy(
        strategy_id=item.get("strategy_id", strategy_id),
        name=item.get("name", ""),
        config=item.get("config", {}),
        parent_strategy_id=item.get("parent_strategy_id", ""),
        generation=item.get("generation", 0),
    )
    context = FailedRunContext(
        run_id=body.run_id,
        strategy_id=strategy_id,
        failure_reason=body.failure_reason,
        metrics=tuple(body.metrics),
        current_config=strategy.config,
    )

    proposal = mutate_strategy(strategy, context)
    return asdict(proposal)


@router.delete("/strategies/evolutionary/{strategy_id}", status_code=204)
async def delete_evolutionary_strategy(
    request: Request,
    strategy_id: str,
    store: Any = Depends(evo_strategy_store_provider),  # noqa: ANN401, B008
) -> None:
    """Delete an evolutionary strategy."""
    if not await store.remove(strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    await dispatch_event(
        request,
        EvolutionaryStrategyRemoved(payload={"resource_id": strategy_id}),
        stream_id=f"evo_strategy:{strategy_id}",
    )
