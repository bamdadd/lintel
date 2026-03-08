"""AI model and model assignment management endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.routes.ai_providers import (
    InMemoryAIProviderStore,
    get_ai_provider_store,
)
from lintel.contracts.events import ModelRegistered, ModelUpdated, ModelRemoved, ModelAssignmentCreated, ModelAssignmentRemoved
from lintel.contracts.types import Model, ModelAssignment, ModelAssignmentContext
from lintel.domain.event_dispatcher import dispatch_event

router = APIRouter()


class InMemoryModelStore:
    """In-memory store for AI models."""

    def __init__(self) -> None:
        self._models: dict[str, Model] = {}

    async def add(self, model: Model) -> None:
        self._models[model.model_id] = model

    async def get(self, model_id: str) -> Model | None:
        return self._models.get(model_id)

    async def list_all(self) -> list[Model]:
        return list(self._models.values())

    async def list_by_provider(self, provider_id: str) -> list[Model]:
        return [m for m in self._models.values() if m.provider_id == provider_id]

    async def update(self, model: Model) -> None:
        if model.model_id not in self._models:
            msg = f"Model {model.model_id} not found"
            raise KeyError(msg)
        self._models[model.model_id] = model

    async def remove(self, model_id: str) -> None:
        if model_id not in self._models:
            msg = f"Model {model_id} not found"
            raise KeyError(msg)
        del self._models[model_id]


class InMemoryModelAssignmentStore:
    """In-memory store for model assignments."""

    def __init__(self) -> None:
        self._assignments: dict[str, ModelAssignment] = {}

    async def add(self, assignment: ModelAssignment) -> None:
        self._assignments[assignment.assignment_id] = assignment

    async def get(self, assignment_id: str) -> ModelAssignment | None:
        return self._assignments.get(assignment_id)

    async def list_all(self) -> list[ModelAssignment]:
        return list(self._assignments.values())

    async def list_by_model(self, model_id: str) -> list[ModelAssignment]:
        return [a for a in self._assignments.values() if a.model_id == model_id]

    async def list_by_context(
        self,
        context: ModelAssignmentContext,
        context_id: str | None = None,
    ) -> list[ModelAssignment]:
        results = [a for a in self._assignments.values() if a.context == context]
        if context_id is not None:
            results = [a for a in results if a.context_id == context_id]
        return results

    async def remove(self, assignment_id: str) -> None:
        if assignment_id not in self._assignments:
            msg = f"Assignment {assignment_id} not found"
            raise KeyError(msg)
        del self._assignments[assignment_id]

    async def remove_by_model(self, model_id: str) -> None:
        to_remove = [aid for aid, a in self._assignments.items() if a.model_id == model_id]
        for aid in to_remove:
            del self._assignments[aid]


def get_model_store(request: Request) -> InMemoryModelStore:
    """Get model store from app state."""
    return request.app.state.model_store  # type: ignore[no-any-return]


def get_model_assignment_store(request: Request) -> InMemoryModelAssignmentStore:
    """Get model assignment store from app state."""
    return request.app.state.model_assignment_store  # type: ignore[no-any-return]


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
    store: Annotated[InMemoryModelStore, Depends(get_model_store)],
    provider_store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    await dispatch_event(request, ModelRegistered(payload={"resource_id": body.model_id, "model_name": body.model_name}), stream_id=f"model:{body.model_id}")
    return await _enrich_model(model, provider_store)


@router.get("/models")
async def list_models(
    store: Annotated[InMemoryModelStore, Depends(get_model_store)],
    provider_store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    store: Annotated[InMemoryModelStore, Depends(get_model_store)],
    provider_store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    store: Annotated[InMemoryModelStore, Depends(get_model_store)],
    provider_store: Annotated[InMemoryAIProviderStore, Depends(get_ai_provider_store)],
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
    await dispatch_event(request, ModelUpdated(payload={"resource_id": model_id}), stream_id=f"model:{model_id}")
    return await _enrich_model(updated, provider_store)


@router.delete("/models/{model_id}", status_code=204)
async def delete_model(
    request: Request,
    model_id: str,
    store: Annotated[InMemoryModelStore, Depends(get_model_store)],
    assignment_store: Annotated[InMemoryModelAssignmentStore, Depends(get_model_assignment_store)],
) -> None:
    """Remove a model and its assignments."""
    model = await store.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    await assignment_store.remove_by_model(model_id)
    await store.remove(model_id)
    await dispatch_event(request, ModelRemoved(payload={"resource_id": model_id}), stream_id=f"model:{model_id}")


@router.post("/models/{model_id}/assignments", status_code=201)
async def create_model_assignment(
    request: Request,
    model_id: str,
    body: CreateModelAssignmentRequest,
    store: Annotated[InMemoryModelStore, Depends(get_model_store)],
    assignment_store: Annotated[InMemoryModelAssignmentStore, Depends(get_model_assignment_store)],
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
    await dispatch_event(request, ModelAssignmentCreated(payload={"resource_id": body.assignment_id, "model_id": model_id}), stream_id=f"model:{model_id}")
    return asdict(assignment)


@router.get("/models/{model_id}/assignments")
async def list_model_assignments(
    model_id: str,
    store: Annotated[InMemoryModelStore, Depends(get_model_store)],
    assignment_store: Annotated[InMemoryModelAssignmentStore, Depends(get_model_assignment_store)],
) -> list[dict[str, Any]]:
    """List assignments for a model."""
    model = await store.get(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    assignments = await assignment_store.list_by_model(model_id)
    return [asdict(a) for a in assignments]


@router.get("/model-assignments")
async def list_all_assignments(
    assignment_store: Annotated[InMemoryModelAssignmentStore, Depends(get_model_assignment_store)],
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
    assignment_store: Annotated[InMemoryModelAssignmentStore, Depends(get_model_assignment_store)],
) -> None:
    """Remove a model assignment."""
    assignment = await assignment_store.get(assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="Assignment not found")
    await assignment_store.remove(assignment_id)
    await dispatch_event(request, ModelAssignmentRemoved(payload={"resource_id": assignment_id}), stream_id="model_assignments")
