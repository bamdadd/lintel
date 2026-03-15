"""Agent operation endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.agent_definitions_api.store import AgentDefinitionStore
from lintel.agents.commands import ScheduleAgentStep
from lintel.agents.events import (
    AgentDefinitionCreated,
    AgentDefinitionRemoved,
    AgentDefinitionUpdated,
)
from lintel.agents.types import AgentRole
from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.contracts.types import ThreadRef

_VALID_ROLES = frozenset(role.value for role in AgentRole)

agent_definition_store_provider = StoreProvider()

router = APIRouter()


class ScheduleAgentStepRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    agent_role: AgentRole
    step_name: str
    context: dict[str, Any] = {}


class TestPromptRequest(BaseModel):
    agent_role: AgentRole
    messages: list[dict[str, str]]


@router.get("/agents/roles")
async def list_agent_roles() -> list[str]:
    return [role.value for role in AgentRole]


@router.post("/agents/test-prompt")
async def test_prompt(body: TestPromptRequest) -> dict[str, Any]:
    """Test a prompt against an agent role (dry-run, returns echo)."""
    return {
        "agent_role": body.agent_role.value,
        "messages": body.messages,
        "response": {
            "content": f"[dry-run] Echo from {body.agent_role.value} agent",
            "usage": {"input_tokens": 0, "output_tokens": 0},
            "model": "dry-run",
        },
    }


@router.post("/agents/steps", status_code=201)
async def schedule_agent_step(
    body: ScheduleAgentStepRequest,
) -> dict[str, Any]:
    thread_ref = ThreadRef(
        workspace_id=body.workspace_id,
        channel_id=body.channel_id,
        thread_ts=body.thread_ts,
    )
    command = ScheduleAgentStep(
        thread_ref=thread_ref,
        agent_role=body.agent_role,
        step_name=body.step_name,
        context=body.context,
        correlation_id=uuid4(),
    )
    return asdict(command)


# --- Custom Agent Definition models and endpoints ---


class CreateAgentDefinitionRequest(BaseModel):
    agent_id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    description: str
    system_prompt: str
    max_tokens: int = 4096
    temperature: float = 0.0
    allowed_skills: list[str] = []
    role: str


class UpdateAgentDefinitionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    max_tokens: int | None = None
    temperature: float | None = None
    allowed_skills: list[str] | None = None
    role: str | None = None


@router.post("/agents/definitions", status_code=201)
async def create_agent_definition(
    body: CreateAgentDefinitionRequest,
    request: Request,
    store: AgentDefinitionStore = Depends(agent_definition_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Create a custom agent definition."""
    definition = body.model_dump()
    try:
        result = await store.create(definition)
    except ValueError:
        raise HTTPException(  # noqa: B904
            status_code=409,
            detail=(f"Agent definition '{body.agent_id}' already exists"),
        )
    await dispatch_event(
        request,
        AgentDefinitionCreated(payload={"resource_id": body.agent_id}),
        stream_id=f"agent_definition:{body.agent_id}",
    )
    return result


@router.get("/agents/definitions")
async def list_agent_definitions(
    store: AgentDefinitionStore = Depends(agent_definition_store_provider),  # noqa: B008
) -> list[dict[str, Any]]:
    """List all custom agent definitions."""
    return await store.list_all()


@router.get("/agents/definitions/{agent_id}")
async def get_agent_definition(
    agent_id: str,
    store: AgentDefinitionStore = Depends(agent_definition_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Get a specific custom agent definition."""
    definition = await store.get(agent_id)
    if definition is None:
        raise HTTPException(
            status_code=404,
            detail=f"Agent definition '{agent_id}' not found",
        )
    return definition


@router.patch("/agents/definitions/{agent_id}")
async def update_agent_definition(
    agent_id: str,
    body: UpdateAgentDefinitionRequest,
    request: Request,
    store: AgentDefinitionStore = Depends(agent_definition_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Update a custom agent definition (partial)."""
    updates = body.model_dump(exclude_none=True)
    try:
        result = await store.update(agent_id, updates)
    except KeyError:
        raise HTTPException(  # noqa: B904
            status_code=404,
            detail=f"Agent definition '{agent_id}' not found",
        )
    await dispatch_event(
        request,
        AgentDefinitionUpdated(payload={"resource_id": agent_id}),
        stream_id=f"agent_definition:{agent_id}",
    )
    return result


@router.delete("/agents/definitions/{agent_id}", status_code=204)
async def delete_agent_definition(
    agent_id: str,
    request: Request,
    store: AgentDefinitionStore = Depends(agent_definition_store_provider),  # noqa: B008
) -> None:
    """Delete a custom agent definition."""
    try:
        await store.delete(agent_id)
    except KeyError:
        raise HTTPException(  # noqa: B904
            status_code=404,
            detail=f"Agent definition '{agent_id}' not found",
        )
    await dispatch_event(
        request,
        AgentDefinitionRemoved(payload={"resource_id": agent_id}),
        stream_id=f"agent_definition:{agent_id}",
    )
