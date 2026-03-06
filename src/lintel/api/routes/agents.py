"""Agent operation endpoints."""

from dataclasses import asdict
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from lintel.contracts.commands import ScheduleAgentStep
from lintel.contracts.types import AgentRole, ModelPolicy, ThreadRef

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
