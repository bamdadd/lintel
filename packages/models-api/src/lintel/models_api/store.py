"""In-memory stores for AI models and model assignments."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.models.types import Model, ModelAssignment, ModelAssignmentContext


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
