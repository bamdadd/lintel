"""Skill registration and invocation endpoints."""

from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.types import SkillDescriptor, SkillExecutionMode, SkillResult

router = APIRouter()


# ---------------------------------------------------------------------------
# In-memory skill store (placeholder until a real SkillRegistry is wired)
# ---------------------------------------------------------------------------


class InMemorySkillStore:
    """Minimal in-memory store satisfying the SkillRegistry protocol shape."""

    def __init__(self) -> None:
        self._skills: dict[str, SkillDescriptor] = {}
        self._metadata: dict[str, dict[str, Any]] = {}

    async def register(
        self,
        skill_id: str,
        version: str,
        name: str,
        input_schema: dict[str, Any],
        output_schema: dict[str, Any],
        execution_mode: str,
    ) -> SkillDescriptor:
        descriptor = SkillDescriptor(
            name=name,
            version=version,
            input_schema=input_schema,
            output_schema=output_schema,
            execution_mode=SkillExecutionMode(execution_mode),
        )
        self._skills[skill_id] = descriptor
        return descriptor

    async def invoke(
        self,
        skill_id: str,
        input_data: dict[str, Any],
        context: dict[str, Any],
    ) -> SkillResult:
        if skill_id not in self._skills:
            msg = f"Skill {skill_id} not found"
            raise KeyError(msg)
        # Stub: real implementation would dispatch to the skill runtime.
        return SkillResult(success=True, output={"echo": input_data})

    async def delete(self, skill_id: str) -> None:
        if skill_id not in self._skills:
            msg = f"Skill {skill_id} not found"
            raise KeyError(msg)
        del self._skills[skill_id]
        self._metadata.pop(skill_id, None)

    async def list_skills(self) -> dict[str, SkillDescriptor]:
        return dict(self._skills)


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------


def get_skill_store(request: Request) -> InMemorySkillStore:
    """Read the skill store from app state."""
    return request.app.state.skill_store  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RegisterSkillRequest(BaseModel):
    skill_id: str
    version: str
    name: str
    description: str = ""
    content: str = ""
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
    store: Annotated[InMemorySkillStore, Depends(get_skill_store)],
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
    store._metadata[body.skill_id] = {"description": body.description, "content": body.content}
    return {"skill_id": body.skill_id, **asdict(descriptor), **store._metadata[body.skill_id]}


@router.get("/skills")
async def list_skills(
    store: Annotated[InMemorySkillStore, Depends(get_skill_store)],
) -> list[dict[str, Any]]:
    skills = await store.list_skills()
    return [
        {"skill_id": sid, **asdict(desc), **store._metadata.get(sid, {})}
        for sid, desc in skills.items()
    ]


@router.get("/skills/{skill_id}")
async def get_skill(
    skill_id: str,
    store: Annotated[InMemorySkillStore, Depends(get_skill_store)],
) -> dict[str, Any]:
    skills = await store.list_skills()
    if skill_id not in skills:
        raise HTTPException(status_code=404, detail="Skill not found")
    return {"skill_id": skill_id, **asdict(skills[skill_id]), **store._metadata.get(skill_id, {})}


@router.delete("/skills/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    store: Annotated[InMemorySkillStore, Depends(get_skill_store)],
) -> None:
    """Delete a registered skill."""
    try:
        await store.delete(skill_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")  # noqa: B904


@router.post("/skills/{skill_id}/invoke")
async def invoke_skill(
    skill_id: str,
    body: InvokeSkillRequest,
    store: Annotated[InMemorySkillStore, Depends(get_skill_store)],
) -> dict[str, Any]:
    try:
        result = await store.invoke(
            skill_id=skill_id,
            input_data=body.input_data,
            context=body.context,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="Skill not found")  # noqa: B904
    return asdict(result)
