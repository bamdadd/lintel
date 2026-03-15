"""AI model and model assignment management endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.ai_providers_api.store import InMemoryAIProviderStore
from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.models.events import (
    ModelAssignmentCreated,
    ModelAssignmentRemoved,
    ModelRegistered,
    ModelRemoved,
    ModelUpdated,
)
from lintel.models.types import Model, ModelAssignment, ModelAssignmentContext
from lintel.models_api.store import InMemoryModelAssignmentStore, InMemoryModelStore

router = APIRouter()

model_store_provider: StoreProvider = StoreProvider()
model_assignment_store_provider: StoreProvider = StoreProvider()
ai_provider_store_provider: StoreProvider = StoreProvider()


class CreateModelRequest(BaseModel):
    model_id: str = Field(default_factory=lambda: str(uuid4()))
    provider_id: str
    name: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0
    is_default: bool = False
    capabilities: list[str] = []
    config: dict[str, Any] = {}


class UpdateModelRequest(BaseModel):
    name: str | None = None
    model_name: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    is_default: bool | None = None
    capabilities: list[str] | None = None
    config: dict[str, Any] | None = None


class CreateModelAssignmentRequest(BaseModel):
    assignment_id: str = Field(default_factory=lambda: str(uuid4()))
    context: ModelAssignmentContext
    context_id: str
    priority: int = 0


async def _enrich_model(
    model: Model,
    provider_store: InMemoryAIProviderStore,
) -> dict[str, Any]:
    """Convert model to dict and add provider info."""
    d = asdict(model)
    d["capabilities"] = list(model.capabilities)
    provider = await provider_store.get(model.provider_id)
    if provider:
        d["provider_name"] = provider.name
        d["provider_type"] = provider.provider_type.value
    else:
        d["provider_name"] = ""
        d["provider_type"] = ""
    return d


@router.post("/models", status_code=201)
async def create_model(
    request: Request,
    body: CreateModelRequest,
    store: InMemoryModelStore = Depends(model_store_provider),  # noqa: B008
    provider_store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Register an AI model."""
    all_providers = await provider_store.list_all()
    if not all_providers:
        raise HTTPException(
            status_code=409,
            detail="No AI providers configured. Please add a provider first"
            " at /ai-providers before adding models.",
        )
    provider = await provider_store.get(body.provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    existing = await store.get(body.model_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Model already exists")
    model = Model(
        model_id=body.model_id,
        provider_id=body.provider_id,
        name=body.name,
        model_name=body.model_name,
        max_tokens=body.max_tokens,
        temperature=body.temperature,
        is_default=body.is_default,
        capabilities=tuple(body.capabilities),
        config=body.config or None,
    )
    await store.add(model)
    await dispatch_event(
        request,
        ModelRegistered(payload={"resource_id": body.model_id, "model_name": body.model_name}),
        stream_id=f"model:{body.model_id}",
    )
    return await _enrich_model(model, provider_store)


@router.get("/models")
async def list_models(
    store: InMemoryModelStore = Depends(model_store_provider),  # noqa: B008
    provider_store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
    provider_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all models, optionally filtered by provider."""
    if provider_id:
        models = await store.list_by_provider(provider_id)
    else:
        models = await store.list_all()
    return [await _enrich_model(m, provider_store) for m in models]


@router.get("/models/{model_id}")
async def get_model(
    model_id: str,
    store: InMemoryModelStore = Depends(model_store_provider),  # noqa: B008
    provider_store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific model."""
    model = await store.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return await _enrich_model(model, provider_store)


@router.patch("/models/{model_id}")
async def update_model(
    request: Request,
    model_id: str,
    body: UpdateModelRequest,
    store: InMemoryModelStore = Depends(model_store_provider),  # noqa: B008
    provider_store: InMemoryAIProviderStore = Depends(ai_provider_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Update a model's configuration."""
    model = await store.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    current = asdict(model)
    updates = body.model_dump(exclude_none=True)
    if "capabilities" in updates:
        updates["capabilities"] = tuple(updates["capabilities"])
    merged = {**current, **updates}
    updated = Model(**merged)
    await store.update(updated)
    await dispatch_event(
        request, ModelUpdated(payload={"resource_id": model_id}), stream_id=f"model:{model_id}"
    )
    # Invalidate model router default cache when default model changes
    if "is_default" in updates:
        model_router = getattr(request.app.state, "model_router", None)
        if model_router is not None and hasattr(model_router, "_cached_default"):
            model_router._cached_default = None
    return await _enrich_model(updated, provider_store)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    request: Request,
    model_id: str,
    store: InMemoryModelStore = Depends(model_store_provider),  # noqa: B008
    assignment_store: InMemoryModelAssignmentStore = Depends(  # noqa: B008
        model_assignment_store_provider,
    ),
) -> None:
    """Remove a model and its assignments."""
    model = await store.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    await assignment_store.remove_by_model(model_id)
    await store.remove(model_id)
    await dispatch_event(
        request, ModelRemoved(payload={"resource_id": model_id}), stream_id=f"model:{model_id}"
    )


@router.post("/models/{model_id}/assignments", status_code=201)
async def create_model_assignment(
    request: Request,
    model_id: str,
    body: CreateModelAssignmentRequest,
    store: InMemoryModelStore = Depends(model_store_provider),  # noqa: B008
    assignment_store: InMemoryModelAssignmentStore = Depends(  # noqa: B008
        model_assignment_store_provider,
    ),
) -> dict[str, Any]:
    """Create an assignment for a model."""
    model = await store.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    assignment = ModelAssignment(
        assignment_id=body.assignment_id,
        model_id=model_id,
        context=body.context,
        context_id=body.context_id,
        priority=body.priority,
    )
    await assignment_store.add(assignment)
    await dispatch_event(
        request,
        ModelAssignmentCreated(payload={"resource_id": body.assignment_id, "model_id": model_id}),
        stream_id=f"model:{model_id}",
    )
    return asdict(assignment)


@router.get("/models/{model_id}/assignments")
async def list_model_assignments(
    model_id: str,
    store: InMemoryModelStore = Depends(model_store_provider),  # noqa: B008
    assignment_store: InMemoryModelAssignmentStore = Depends(  # noqa: B008
        model_assignment_store_provider,
    ),
) -> list[dict[str, Any]]:
    """List assignments for a model."""
    model = await store.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    assignments = await assignment_store.list_by_model(model_id)
    return [asdict(a) for a in assignments]


@router.get("/model-assignments")
async def list_all_assignments(
    assignment_store: InMemoryModelAssignmentStore = Depends(  # noqa: B008
        model_assignment_store_provider,
    ),
    context: ModelAssignmentContext | None = None,
    context_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all assignments, optionally filtered by context."""
    if context:
        assignments = await assignment_store.list_by_context(context, context_id)
    else:
        assignments = await assignment_store.list_all()
    return [asdict(a) for a in assignments]


@router.delete("/model-assignments/{assignment_id}", status_code=204)
async def delete_model_assignment(
    request: Request,
    assignment_id: str,
    assignment_store: InMemoryModelAssignmentStore = Depends(  # noqa: B008
        model_assignment_store_provider,
    ),
) -> None:
    """Remove a model assignment."""
    assignment = await assignment_store.get(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await assignment_store.remove(assignment_id)
    await dispatch_event(
        request,
        ModelAssignmentRemoved(payload={"resource_id": assignment_id}),
        stream_id="model_assignments",
    )
