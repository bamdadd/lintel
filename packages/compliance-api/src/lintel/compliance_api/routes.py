"""Compliance & Governance CRUD endpoints — barrel file.

All route handlers live in domain-specific sub-modules:
  - regulations.py  — Regulation CRUD + templates
  - policies.py     — Compliance policy, procedure, practice, strategy CRUD
  - knowledge.py    — Knowledge entry + extraction run CRUD
  - architecture.py — Architecture decision record CRUD
  - config.py       — Compliance config get/update + overview
  - guardrail_rules.py — Guardrail rule CRUD
"""

from fastapi import APIRouter

from lintel.compliance_api.architecture import (
    architecture_decision_store_provider,
)
from lintel.compliance_api.architecture import (
    router as architecture_router,
)
from lintel.compliance_api.config import router as config_router
from lintel.compliance_api.guardrail_rules import (
    guardrail_rule_store_provider,
)
from lintel.compliance_api.guardrail_rules import (
    router as guardrail_rules_router,
)
from lintel.compliance_api.knowledge import (
    knowledge_entry_store_provider,
    knowledge_extraction_store_provider,
)
from lintel.compliance_api.knowledge import (
    router as knowledge_router,
)
from lintel.compliance_api.policies import (
    compliance_policy_store_provider,
    practice_store_provider,
    procedure_store_provider,
    strategy_store_provider,
)
from lintel.compliance_api.policies import (
    router as policies_router,
)
from lintel.compliance_api.policy_generation import (
    policy_generation_store_provider,
)
from lintel.compliance_api.policy_generation import (
    router as policy_generation_router,
)
from lintel.compliance_api.regulations import (
    regulation_store_provider,
)
from lintel.compliance_api.regulations import (
    router as regulations_router,
)

__all__ = [
    "architecture_decision_store_provider",
    "compliance_policy_store_provider",
    "guardrail_rule_store_provider",
    "knowledge_entry_store_provider",
    "knowledge_extraction_store_provider",
    "policy_generation_store_provider",
    "practice_store_provider",
    "procedure_store_provider",
    "regulation_store_provider",
    "router",
    "strategy_store_provider",
]

router = APIRouter()
router.include_router(regulations_router)
router.include_router(policies_router)
router.include_router(knowledge_router)
router.include_router(architecture_router)
router.include_router(config_router)
router.include_router(policy_generation_router)
router.include_router(guardrail_rules_router)
