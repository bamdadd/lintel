"""Composable agent skill CRUD endpoints (REQ-F033)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.agent_skills_api.store import (
    InMemoryAgentSkillBindingStore,  # noqa: TC001
    InMemoryAgentSkillStore,  # noqa: TC001
)
from lintel.agent_skills_api.types import AgentSkill, AgentSkillBinding, SkillCategory
from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.domain.events import (
    AgentSkillBound,
    AgentSkillCreated,
    AgentSkillRemoved,
    AgentSkillUnbound,
    AgentSkillUpdated,
)

router = APIRouter()

agent_skill_store_provider: StoreProvider[InMemoryAgentSkillStore] = StoreProvider()
agent_skill_binding_store_provider: StoreProvider[InMemoryAgentSkillBindingStore] = StoreProvider()


# --- Request models ---


class CreateAgentSkillRequest(BaseModel):
    skill_id: str = ""
    name: str
    description: str = ""
    category: SkillCategory = SkillCategory.CUSTOM
    version: str = "1.0.0"
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    required_tools: list[str] = Field(default_factory=list)
    active: bool = True
    project_id: str = ""


class UpdateAgentSkillRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    category: SkillCategory | None = None
    version: str | None = None
    parameters_schema: dict[str, Any] | None = None
    required_tools: list[str] | None = None
    active: bool | None = None


class CreateAgentSkillBindingRequest(BaseModel):
    binding_id: str = ""
    agent_definition_id: str
    skill_id: str
    configuration: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    active: bool = True


# --- Fixed-path routes MUST come before {skill_id} parameterized routes ---


@router.get("/agent-skills/categories")
async def list_categories() -> list[str]:
    return [c.value for c in SkillCategory]


@router.post("/agent-skills/bindings", status_code=201)
async def create_agent_skill_binding(
    request: Request,
    body: CreateAgentSkillBindingRequest,
    binding_store: Annotated[
        InMemoryAgentSkillBindingStore, Depends(agent_skill_binding_store_provider)
    ],
) -> dict[str, Any]:
    from uuid import uuid4

    binding = AgentSkillBinding(
        binding_id=body.binding_id or str(uuid4()),
        agent_definition_id=body.agent_definition_id,
        skill_id=body.skill_id,
        configuration=body.configuration,
        priority=body.priority,
        active=body.active,
    )
    result = await binding_store.add(binding)
    await dispatch_event(
        request,
        AgentSkillBound(
            payload={
                "resource_id": binding.binding_id,
                "agent_definition_id": body.agent_definition_id,
                "skill_id": body.skill_id,
            },
        ),
        stream_id=f"agent-skill-binding:{binding.binding_id}",
    )
    return result


@router.get("/agent-skills/bindings")
async def list_agent_skill_bindings(
    binding_store: Annotated[
        InMemoryAgentSkillBindingStore, Depends(agent_skill_binding_store_provider)
    ],
) -> list[dict[str, Any]]:
    return await binding_store.list_all()


@router.delete("/agent-skills/bindings/{binding_id}", status_code=204)
async def delete_agent_skill_binding(
    request: Request,
    binding_id: str,
    binding_store: Annotated[
        InMemoryAgentSkillBindingStore, Depends(agent_skill_binding_store_provider)
    ],
) -> None:
    if not await binding_store.remove(binding_id):
        raise HTTPException(status_code=404, detail="Agent skill binding not found")
    await dispatch_event(
        request,
        AgentSkillUnbound(payload={"resource_id": binding_id}),
        stream_id=f"agent-skill-binding:{binding_id}",
    )


@router.get("/agent-skills/agents/{agent_definition_id}/skills")
async def list_skills_for_agent(
    agent_definition_id: str,
    binding_store: Annotated[
        InMemoryAgentSkillBindingStore, Depends(agent_skill_binding_store_provider)
    ],
) -> list[dict[str, Any]]:
    return await binding_store.list_by_agent(agent_definition_id)


# --- Skill CRUD routes (parameterized paths last) ---


@router.post("/agent-skills", status_code=201)
async def create_agent_skill(
    request: Request,
    body: CreateAgentSkillRequest,
    store: Annotated[InMemoryAgentSkillStore, Depends(agent_skill_store_provider)],
) -> dict[str, Any]:
    from uuid import uuid4

    skill = AgentSkill(
        skill_id=body.skill_id or str(uuid4()),
        name=body.name,
        description=body.description,
        category=body.category,
        version=body.version,
        parameters_schema=body.parameters_schema,
        required_tools=tuple(body.required_tools),
        active=body.active,
        project_id=body.project_id,
    )
    result = await store.add(skill)
    await dispatch_event(
        request,
        AgentSkillCreated(
            payload={"resource_id": skill.skill_id, "name": skill.name},
        ),
        stream_id=f"agent-skill:{skill.skill_id}",
    )
    return result


@router.get("/agent-skills")
async def list_agent_skills(
    store: Annotated[InMemoryAgentSkillStore, Depends(agent_skill_store_provider)],
) -> list[dict[str, Any]]:
    return await store.list_all()


@router.get("/agent-skills/{skill_id}")
async def get_agent_skill(
    skill_id: str,
    store: Annotated[InMemoryAgentSkillStore, Depends(agent_skill_store_provider)],
) -> dict[str, Any]:
    item = await store.get(skill_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Agent skill not found")
    return item


@router.patch("/agent-skills/{skill_id}")
async def update_agent_skill(
    request: Request,
    skill_id: str,
    body: UpdateAgentSkillRequest,
    store: Annotated[InMemoryAgentSkillStore, Depends(agent_skill_store_provider)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "required_tools" in updates:
        updates["required_tools"] = tuple(updates["required_tools"])
    result = await store.update(skill_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent skill not found")
    await dispatch_event(
        request,
        AgentSkillUpdated(
            payload={"resource_id": skill_id, **updates},
        ),
        stream_id=f"agent-skill:{skill_id}",
    )
    return result


@router.delete("/agent-skills/{skill_id}", status_code=204)
async def delete_agent_skill(
    request: Request,
    skill_id: str,
    store: Annotated[InMemoryAgentSkillStore, Depends(agent_skill_store_provider)],
) -> None:
    if not await store.remove(skill_id):
        raise HTTPException(status_code=404, detail="Agent skill not found")
    await dispatch_event(
        request,
        AgentSkillRemoved(payload={"resource_id": skill_id}),
        stream_id=f"agent-skill:{skill_id}",
    )
