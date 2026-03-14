"""Variable CRUD endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.container import AppContainer
from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.contracts.events import VariableCreated, VariableRemoved, VariableUpdated
from lintel.contracts.types import Variable

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory store
# ---------------------------------------------------------------------------


class InMemoryVariableStore:
    """Simple in-memory store for variables."""

    def __init__(self) -> None:
        self._variables: dict[str, Variable] = {}

    async def add(self, variable: Variable) -> None:
        self._variables[variable.variable_id] = variable

    async def get(self, variable_id: str) -> Variable | None:
        return self._variables.get(variable_id)

    async def list_all(
        self,
        environment_id: str | None = None,
    ) -> list[Variable]:
        items = list(self._variables.values())
        if environment_id is not None:
            items = [v for v in items if v.environment_id == environment_id]
        return items

    async def update(self, variable: Variable) -> None:
        if variable.variable_id not in self._variables:
            msg = f"Variable {variable.variable_id} not found"
            raise KeyError(msg)
        self._variables[variable.variable_id] = variable

    async def remove(self, variable_id: str) -> None:
        if variable_id not in self._variables:
            msg = f"Variable {variable_id} not found"
            raise KeyError(msg)
        del self._variables[variable_id]


def get_variable_store(request: Request) -> InMemoryVariableStore:
    """Kept for backward compat."""
    return request.app.state.variable_store  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateVariableRequest(BaseModel):
    variable_id: str = Field(default_factory=lambda: str(uuid4()))
    key: str
    value: str
    environment_id: str = ""
    is_secret: bool = False


class UpdateVariableRequest(BaseModel):
    value: str | None = None
    is_secret: bool | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_secret(value: str) -> str:
    """Return first 4 characters followed by '****'."""
    if len(value) <= 4:
        return value[: len(value)] + "****"
    return value[:4] + "****"


def _serialize(variable: Variable) -> dict[str, Any]:
    """Convert a Variable to dict, masking the value when secret."""
    data = asdict(variable)
    if variable.is_secret:
        data["value"] = _mask_secret(variable.value)
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/variables", status_code=201)
@inject
async def create_variable(
    body: CreateVariableRequest,
    request: Request,
    store: InMemoryVariableStore = Depends(Provide[AppContainer.variable_store]),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.get(body.variable_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Variable already exists")
    variable = Variable(
        variable_id=body.variable_id,
        key=body.key,
        value=body.value,
        environment_id=body.environment_id,
        is_secret=body.is_secret,
    )
    await store.add(variable)
    await dispatch_event(
        request,
        VariableCreated(payload={"resource_id": variable.variable_id}),
        stream_id=f"variable:{variable.variable_id}",
    )
    return _serialize(variable)


@router.get("/variables")
@inject
async def list_variables(
    store: InMemoryVariableStore = Depends(Provide[AppContainer.variable_store]),  # noqa: B008
    environment_id: str | None = None,
) -> list[dict[str, Any]]:
    variables = await store.list_all(
        environment_id=environment_id,
    )
    return [_serialize(v) for v in variables]


@router.get("/variables/{variable_id}")
@inject
async def get_variable(
    variable_id: str,
    store: InMemoryVariableStore = Depends(Provide[AppContainer.variable_store]),  # noqa: B008
) -> dict[str, Any]:
    variable = await store.get(variable_id)
    if variable is None:
        raise HTTPException(status_code=404, detail="Variable not found")
    return _serialize(variable)


@router.patch("/variables/{variable_id}")
@inject
async def update_variable(
    variable_id: str,
    body: UpdateVariableRequest,
    request: Request,
    store: InMemoryVariableStore = Depends(Provide[AppContainer.variable_store]),  # noqa: B008
) -> dict[str, Any]:
    variable = await store.get(variable_id)
    if variable is None:
        raise HTTPException(status_code=404, detail="Variable not found")
    updates = body.model_dump(exclude_none=True)
    updated = Variable(**{**asdict(variable), **updates})
    await store.update(updated)
    await dispatch_event(
        request,
        VariableUpdated(payload={"resource_id": variable_id}),
        stream_id=f"variable:{variable_id}",
    )
    return _serialize(updated)


@router.delete("/variables/{variable_id}", status_code=204)
@inject
async def delete_variable(
    variable_id: str,
    request: Request,
    store: InMemoryVariableStore = Depends(Provide[AppContainer.variable_store]),  # noqa: B008
) -> None:
    variable = await store.get(variable_id)
    if variable is None:
        raise HTTPException(status_code=404, detail="Variable not found")
    await store.remove(variable_id)
    await dispatch_event(
        request,
        VariableRemoved(payload={"resource_id": variable_id}),
        stream_id=f"variable:{variable_id}",
    )
