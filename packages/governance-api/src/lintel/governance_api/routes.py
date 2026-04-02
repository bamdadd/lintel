"""Governance API endpoints — barrel module."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.governance_api.audit import (
    CreateGovernanceAuditRequest,
    governance_audit_store_provider,
)
from lintel.governance_api.audit import (
    router as audit_router,
)
from lintel.governance_api.policies import (
    CreateGovernancePolicyRequest,
    UpdateGovernancePolicyRequest,
    governance_policy_store_provider,
)
from lintel.governance_api.policies import (
    router as policies_router,
)

__all__ = [
    "CreateGovernanceAuditRequest",
    "CreateGovernancePolicyRequest",
    "UpdateGovernancePolicyRequest",
    "governance_audit_store_provider",
    "governance_policy_store_provider",
    "router",
]

router = APIRouter()
router.include_router(policies_router)
router.include_router(audit_router)
