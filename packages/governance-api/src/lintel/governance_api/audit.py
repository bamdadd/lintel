"""Governance audit entry CRUD endpoints."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.contracts.events import EventEnvelope
from lintel.domain.events import (
    AgentActionAllowed,
    AgentActionApprovalRequested,
    AgentActionDenied,
)
from lintel.domain.types import (
    ActionScope,
    GovernanceAuditEntry,
    GovernanceDecision,
)

router = APIRouter()

governance_audit_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


class CreateGovernanceAuditRequest(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    policy_id: str = ""
    agent_id: str = ""
    agent_role: str = ""
    action: str = ""
    action_args: str = ""
    scope: ActionScope = ActionScope.TOOL_CALL
    decision: GovernanceDecision = GovernanceDecision.ALLOW
    trust_score: float = 0.0
    reason: str = ""
    timestamp: str = ""
    tags: list[str] = []


_DECISION_EVENTS: dict[GovernanceDecision, Callable[[str], EventEnvelope]] = {
    GovernanceDecision.ALLOW: lambda entry_id: AgentActionAllowed(
        payload={"resource_id": entry_id}
    ),
    GovernanceDecision.DENY: lambda entry_id: AgentActionDenied(payload={"resource_id": entry_id}),
    GovernanceDecision.REQUIRE_APPROVAL: lambda entry_id: AgentActionApprovalRequested(
        payload={"resource_id": entry_id}
    ),
}


@router.post("/governance/audit", status_code=201)
async def record_governance_audit(
    request: Request,
    body: CreateGovernanceAuditRequest,
    store: Annotated[ComplianceStore, Depends(governance_audit_store_provider)],
) -> dict[str, Any]:
    entry = GovernanceAuditEntry(
        entry_id=body.entry_id,
        project_id=body.project_id,
        policy_id=body.policy_id,
        agent_id=body.agent_id,
        agent_role=body.agent_role,
        action=body.action,
        action_args=body.action_args,
        scope=body.scope,
        decision=body.decision,
        trust_score=body.trust_score,
        reason=body.reason,
        timestamp=body.timestamp,
        tags=tuple(body.tags),
    )
    result = await store.add(entry)
    event_factory = _DECISION_EVENTS.get(body.decision)
    if event_factory is not None:
        await dispatch_event(
            request,
            event_factory(body.entry_id),
            stream_id=f"governance-audit:{body.entry_id}",
        )
    return result


@router.get("/governance/audit")
async def list_governance_audit(
    store: Annotated[ComplianceStore, Depends(governance_audit_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/governance/audit/{entry_id}")
async def get_governance_audit(
    entry_id: str,
    store: Annotated[ComplianceStore, Depends(governance_audit_store_provider)],
) -> dict[str, Any]:
    item = await store.get(entry_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Governance audit entry not found")
    return item
