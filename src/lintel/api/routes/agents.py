"""Agent operation endpoints."""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.commands import ScheduleAgentStep
from lintel.contracts.types import AgentRole, ModelPolicy, ThreadRef


class AgentDefinitionStore:
    """In-memory store for user-defined agent definitions."""

    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, Any]] = {}

    def list_all(self) -> list[dict[str, Any]]:
        return list(self._definitions.values())

    def get(self, agent_id: str) -> dict[str, Any] | None:
        return self._definitions.get(agent_id)

    def create(self, definition: dict[str, Any]) -> dict[str, Any]:
        agent_id = definition["agent_id"]
        if agent_id in self._definitions:
            raise ValueError(f"Agent definition '{agent_id}' already exists")
        self._definitions[agent_id] = definition
        return definition

    def update(self, agent_id: str, updates: dict[str, Any]) -> dict[str, Any]:
        if agent_id not in self._definitions:
            raise KeyError(agent_id)
        self._definitions[agent_id].update(updates)
        return self._definitions[agent_id]

    def delete(self, agent_id: str) -> None:
        if agent_id not in self._definitions:
            raise KeyError(agent_id)
        del self._definitions[agent_id]


def get_agent_definition_store(
    request: Request,
) -> AgentDefinitionStore:
    """Get agent definition store from app state."""
    if not hasattr(request.app.state, "agent_definition_store"):
        request.app.state.agent_definition_store = AgentDefinitionStore()
    return request.app.state.agent_definition_store  # type: ignore[no-any-return]


router = APIRouter()


def get_model_policies(request: Request) -> dict[str, dict[str, Any]]:
    """Get mutable model policies from app state."""
    if not hasattr(request.app.state, "model_policies"):
        request.app.state.model_policies = {
            role.value: asdict(ModelPolicy("anthropic", "claude-sonnet-4-20250514"))
            for role in AgentRole
        }
    return request.app.state.model_policies  # type: ignore[no-any-return]


class ScheduleAgentStepRequest(BaseModel):
    workspace_id: str
    channel_id: str
    thread_ts: str
    agent_role: AgentRole
    step_name: str
    context: dict[str, Any] = {}


class UpdateModelPolicyRequest(BaseModel):
    provider: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0


class TestPromptRequest(BaseModel):
    agent_role: AgentRole
    messages: list[dict[str, str]]


@router.get("/agents/roles")
async def list_agent_roles() -> list[str]:
    return [role.value for role in AgentRole]


@router.get("/agents/policies")
async def list_model_policies(request: Request) -> dict[str, dict[str, Any]]:
    """Get model policies for all agent roles."""
    return get_model_policies(request)


@router.get("/agents/policies/{role}")
async def get_model_policy(role: str, request: Request) -> dict[str, Any]:
    """Get model policy for a specific agent role."""
    policies = get_model_policies(request)
    if role not in policies:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"role": role, **policies[role]}


@router.put("/agents/policies/{role}")
async def update_model_policy(
    role: str, body: UpdateModelPolicyRequest, request: Request
) -> dict[str, Any]:
    """Update model policy for a specific agent role."""
    try:
        AgentRole(role)
    except ValueError:
        raise HTTPException(status_code=404, detail="Role not found")  # noqa: B904
    policies = get_model_policies(request)
    policies[role] = {
        "provider": body.provider,
        "model_name": body.model_name,
        "max_tokens": body.max_tokens,
        "temperature": body.temperature,
    }
    return {"role": role, **policies[role]}


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


class ModelPolicyRequest(BaseModel):
    provider: str
    model_name: str
    max_tokens: int = 4096
    temperature: float = 0.0


class CreateAgentDefinitionRequest(BaseModel):
    agent_id: str
    name: str
    description: str
    system_prompt: str
    model_policy: ModelPolicyRequest
    allowed_skills: list[str] = []
    role: str


class UpdateAgentDefinitionRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    model_policy: ModelPolicyRequest | None = None
    allowed_skills: list[str] | None = None
    role: str | None = None


AgentDefStoreDep = Annotated[AgentDefinitionStore, Depends(get_agent_definition_store)]


@router.post("/agents/definitions", status_code=201)
async def create_agent_definition(
    body: CreateAgentDefinitionRequest,
    store: AgentDefStoreDep,
) -> dict[str, Any]:
    """Create a custom agent definition."""
    definition = body.model_dump()
    definition["model_policy"] = body.model_policy.model_dump()
    try:
        return store.create(definition)
    except ValueError:
        raise HTTPException(  # noqa: B904
            status_code=409,
            detail=(f"Agent definition '{body.agent_id}' already exists"),
        )


@router.get("/agents/definitions")
async def list_agent_definitions(
    store: AgentDefStoreDep,
) -> list[dict[str, Any]]:
    """List all custom agent definitions."""
    return store.list_all()


@router.get("/agents/definitions/{agent_id}")
async def get_agent_definition(
    agent_id: str,
    store: AgentDefStoreDep,
) -> dict[str, Any]:
    """Get a specific custom agent definition."""
    definition = store.get(agent_id)
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
    store: AgentDefStoreDep,
) -> dict[str, Any]:
    """Update a custom agent definition (partial)."""
    updates = body.model_dump(exclude_none=True)
    if "model_policy" in updates:
        updates["model_policy"] = body.model_policy.model_dump()  # type: ignore[union-attr]
    try:
        return store.update(agent_id, updates)
    except KeyError:
        raise HTTPException(  # noqa: B904
            status_code=404,
            detail=f"Agent definition '{agent_id}' not found",
        )


@router.delete("/agents/definitions/{agent_id}", status_code=204)
async def delete_agent_definition(
    agent_id: str,
    store: AgentDefStoreDep,
) -> None:
    """Delete a custom agent definition."""
    try:
        store.delete(agent_id)
    except KeyError:
        raise HTTPException(  # noqa: B904
            status_code=404,
            detail=f"Agent definition '{agent_id}' not found",
        )
