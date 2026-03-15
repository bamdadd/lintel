"""Skill registration and invocation endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.agents.events import (
    SkillInvoked,
    SkillRegistered,
    SkillRemoved,
    SkillUpdated,
)
from lintel.agents.types import (
    SkillCategory,
    SkillDescriptor,
    SkillExecutionMode,
    SkillResult,
)
from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.skills_api.store import InMemorySkillStore

router = APIRouter()

skill_store_provider = StoreProvider()


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def _get_metadata(store: InMemorySkillStore, skill_id: str) -> dict[str, Any]:
    """Safely get skill metadata (only exists on in-memory store)."""
    if hasattr(store, "_metadata"):
        return store._metadata.get(skill_id, {})
    return {}


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterSkillRequest(BaseModel):
    skill_id: str = Field(default_factory=lambda: str(uuid4()))
    version: str
    name: str
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    execution_mode: SkillExecutionMode = SkillExecutionMode.INLINE


class InvokeSkillRequest(BaseModel):
    input_data: dict[str, Any] = {}
    context: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/skills", status_code=201)
async def register_skill(
    body: RegisterSkillRequest,
    request: Request,
    store: InMemorySkillStore = Depends(skill_store_provider),  # noqa: B008
) -> dict[str, Any]:
    existing = await store.list_skills()
    if body.skill_id in existing:
        raise HTTPException(status_code=409, detail="Skill already registered")
    descriptor = await store.register(
        skill_id=body.skill_id,
        version=body.version,
        name=body.name,
        input_schema=body.input_schema,
        output_schema=body.output_schema,
        execution_mode=body.execution_mode.value,
    )
    if hasattr(store, "_metadata"):
        store._metadata[body.skill_id] = {
            "description": body.description,
            "category": body.category.value,
        }
    await dispatch_event(
        request,
        SkillRegistered(payload={"resource_id": body.skill_id}),
        stream_id=f"skill:{body.skill_id}",
    )
    return {"skill_id": body.skill_id, **asdict(descriptor), **_get_metadata(store, body.skill_id)}


@router.get("/skills")
async def list_skills(
    store: InMemorySkillStore = Depends(skill_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    skills = await store.list_skills()
    return [
        {"skill_id": sid, **asdict(desc), **_get_metadata(store, sid)}
        for sid, desc in skills.items()
    ]


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    store: InMemorySkillStore = Depends(skill_store_provider),  # noqa: B008
) -> dict[str, Any]:
    skills = await store.list_skills()
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"skill_id": skill_id, **asdict(skills[skill_id]), **_get_metadata(store, skill_id)}


class UpdateSkillRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: SkillCategory | None = None
    version: str | None = None
    execution_mode: SkillExecutionMode | None = None


@router.patch("/skills/{skill_id}")
async def update_skill(
    skill_id: str,
    body: UpdateSkillRequest,
    request: Request,
    store: InMemorySkillStore = Depends(skill_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Update a registered skill."""
    skills = await store.list_skills()
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    descriptor = skills[skill_id]
    updates = body.model_dump(exclude_none=True)
    meta = _get_metadata(store, skill_id)
    if "description" in updates:
        meta["description"] = updates.pop("description")
    if "category" in updates:
        meta["category"] = updates.pop("category").value
    if hasattr(store, "_metadata"):
        store._metadata[skill_id] = meta
    if "execution_mode" in updates:
        updates["execution_mode"] = SkillExecutionMode(updates["execution_mode"])
    for key, val in updates.items():
        object.__setattr__(descriptor, key, val)
    await dispatch_event(
        request, SkillUpdated(payload={"resource_id": skill_id}), stream_id=f"skill:{skill_id}"
    )
    return {"skill_id": skill_id, **asdict(descriptor), **_get_metadata(store, skill_id)}


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    request: Request,
    store: InMemorySkillStore = Depends(skill_store_provider),  # noqa: B008
) -> None:
    """Delete a registered skill."""
    try:
        await store.delete(skill_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")  # noqa: B904
    await dispatch_event(
        request, SkillRemoved(payload={"resource_id": skill_id}), stream_id=f"skill:{skill_id}"
    )


@router.post("/skills/{skill_id}/invoke")
async def invoke_skill(
    skill_id: str,
    body: InvokeSkillRequest,
    request: Request,
    store: InMemorySkillStore = Depends(skill_store_provider),  # noqa: B008
) -> dict[str, Any]:
    try:
        result = await store.invoke(
            skill_id=skill_id,
            input_data=body.input_data,
            context=body.context,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")  # noqa: B904
    await dispatch_event(
        request, SkillInvoked(payload={"resource_id": skill_id}), stream_id=f"skill:{skill_id}"
    )
    return asdict(result)
