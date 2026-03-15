"""Compliance & Governance CRUD endpoints.

Covers: regulations, compliance policies, procedures, practices,
strategies, knowledge entries, and knowledge extraction runs.

KPIs, experiments, and compliance metrics live in the experimentation module.
"""

from dataclasses import asdict
from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api.domain.event_dispatcher import dispatch_event
from lintel.domain.events import (
    ArchitectureDecisionCreated,
    ArchitectureDecisionRemoved,
    ArchitectureDecisionUpdated,
    CompliancePolicyCreated,
    CompliancePolicyRemoved,
    CompliancePolicyUpdated,
    KnowledgeEntryCreated,
    KnowledgeEntryRemoved,
    KnowledgeEntryUpdated,
    KnowledgeExtractionStarted,
    PracticeCreated,
    PracticeRemoved,
    PracticeUpdated,
    ProcedureCreated,
    ProcedureRemoved,
    ProcedureUpdated,
    ProjectUpdated,
    RegulationCreated,
    RegulationRemoved,
    RegulationUpdated,
    StrategyCreated,
    StrategyRemoved,
    StrategyUpdated,
)
from lintel.domain.types import (
    ADRStatus,
    ArchitectureDecision,
    CompliancePolicy,
    ComplianceStatus,
    ExtractionStatus,
    KnowledgeEntry,
    KnowledgeEntryType,
    KnowledgeExtractionRun,
    Practice,
    Procedure,
    Regulation,
    RiskLevel,
    Strategy,
)

router = APIRouter()


# ---------------------------------------------------------------------------
# Generic in-memory store for compliance entities
# ---------------------------------------------------------------------------


class ComplianceStore:
    """Generic in-memory store for any frozen dataclass with an id field."""

    def __init__(self, id_field: str) -> None:
        self._data: dict[str, Any] = {}
        self._id_field = id_field

    def _to_dict(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = asdict(entity)
        for k, v in data.items():
            if isinstance(v, (tuple, frozenset)):
                data[k] = list(v)
        return data

    async def add(self, entity: Any) -> dict[str, Any]:  # noqa: ANN401
        data = self._to_dict(entity)
        self._data[data[self._id_field]] = data
        return data

    async def get(self, entity_id: str) -> dict[str, Any] | None:
        return self._data.get(entity_id)

    async def list_all(self) -> list[dict[str, Any]]:
        return list(self._data.values())

    async def list_by_project(self, project_id: str) -> list[dict[str, Any]]:
        return [d for d in self._data.values() if d.get("project_id") == project_id]

    async def update(self, entity_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
        existing = self._data.get(entity_id)
        if existing is None:
            return None
        merged = {**existing, **data}
        self._data[entity_id] = merged
        return merged

    async def remove(self, entity_id: str) -> bool:
        return self._data.pop(entity_id, None) is not None


# ---------------------------------------------------------------------------
# Store accessors
# ---------------------------------------------------------------------------


def get_regulation_store(request: Request) -> ComplianceStore:
    return request.app.state.regulation_store  # type: ignore[no-any-return]


def get_compliance_policy_store(request: Request) -> ComplianceStore:
    return request.app.state.compliance_policy_store  # type: ignore[no-any-return]


def get_procedure_store(request: Request) -> ComplianceStore:
    return request.app.state.procedure_store  # type: ignore[no-any-return]


def get_practice_store(request: Request) -> ComplianceStore:
    return request.app.state.practice_store  # type: ignore[no-any-return]


def get_strategy_store(request: Request) -> ComplianceStore:
    return request.app.state.strategy_store  # type: ignore[no-any-return]


def get_knowledge_entry_store(request: Request) -> ComplianceStore:
    return request.app.state.knowledge_entry_store  # type: ignore[no-any-return]


def get_knowledge_extraction_store(request: Request) -> ComplianceStore:
    return request.app.state.knowledge_extraction_store  # type: ignore[no-any-return]


def get_architecture_decision_store(request: Request) -> ComplianceStore:
    return request.app.state.architecture_decision_store  # type: ignore[no-any-return]


# ===================== REGULATIONS =====================


class CreateRegulationRequest(BaseModel):
    regulation_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    authority: str = ""
    reference_url: str = ""
    version: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = []


class UpdateRegulationRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    authority: str | None = None
    reference_url: str | None = None
    version: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    tags: list[str] | None = None


@router.post("/regulations", status_code=201)
async def create_regulation(
    request: Request,
    body: CreateRegulationRequest,
    store: Annotated[ComplianceStore, Depends(get_regulation_store)],
) -> dict[str, Any]:
    existing = await store.get(body.regulation_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Regulation already exists")
    regulation = Regulation(
        regulation_id=body.regulation_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        authority=body.authority,
        reference_url=body.reference_url,
        version=body.version,
        status=body.status,
        risk_level=body.risk_level,
        tags=tuple(body.tags),
    )
    result = await store.add(regulation)
    await dispatch_event(
        request,
        RegulationCreated(payload={"resource_id": body.regulation_id, "name": body.name}),
        stream_id=f"regulation:{body.regulation_id}",
    )
    return result


@router.get("/regulations")
async def list_regulations(
    store: Annotated[ComplianceStore, Depends(get_regulation_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/regulations/{regulation_id}")
async def get_regulation(
    regulation_id: str,
    store: Annotated[ComplianceStore, Depends(get_regulation_store)],
) -> dict[str, Any]:
    item = await store.get(regulation_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    return item


@router.patch("/regulations/{regulation_id}")
async def update_regulation(
    request: Request,
    regulation_id: str,
    body: UpdateRegulationRequest,
    store: Annotated[ComplianceStore, Depends(get_regulation_store)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "tags" in updates:
        updates["tags"] = list(updates["tags"])
    result = await store.update(regulation_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Regulation not found")
    await dispatch_event(
        request,
        RegulationUpdated(payload={"resource_id": regulation_id}),
        stream_id=f"regulation:{regulation_id}",
    )
    return result


@router.delete("/regulations/{regulation_id}", status_code=204)
async def remove_regulation(
    request: Request,
    regulation_id: str,
    store: Annotated[ComplianceStore, Depends(get_regulation_store)],
) -> None:
    if not await store.remove(regulation_id):
        raise HTTPException(status_code=404, detail="Regulation not found")
    await dispatch_event(
        request,
        RegulationRemoved(payload={"resource_id": regulation_id}),
        stream_id=f"regulation:{regulation_id}",
    )


# ===================== COMPLIANCE POLICIES =====================


class CreateCompliancePolicyRequest(BaseModel):
    policy_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    regulation_ids: list[str] = []
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.MEDIUM
    review_date: str = ""
    tags: list[str] = []


class UpdateCompliancePolicyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    regulation_ids: list[str] | None = None
    owner: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    review_date: str | None = None
    tags: list[str] | None = None


@router.post("/compliance-policies", status_code=201)
async def create_compliance_policy(
    request: Request,
    body: CreateCompliancePolicyRequest,
    store: Annotated[ComplianceStore, Depends(get_compliance_policy_store)],
) -> dict[str, Any]:
    existing = await store.get(body.policy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Compliance policy already exists")
    policy = CompliancePolicy(
        policy_id=body.policy_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        regulation_ids=tuple(body.regulation_ids),
        owner=body.owner,
        status=body.status,
        risk_level=body.risk_level,
        review_date=body.review_date,
        tags=tuple(body.tags),
    )
    result = await store.add(policy)
    await dispatch_event(
        request,
        CompliancePolicyCreated(payload={"resource_id": body.policy_id, "name": body.name}),
        stream_id=f"compliance_policy:{body.policy_id}",
    )
    return result


@router.get("/compliance-policies")
async def list_compliance_policies(
    store: Annotated[ComplianceStore, Depends(get_compliance_policy_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/compliance-policies/{policy_id}")
async def get_compliance_policy(
    policy_id: str,
    store: Annotated[ComplianceStore, Depends(get_compliance_policy_store)],
) -> dict[str, Any]:
    item = await store.get(policy_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Compliance policy not found")
    return item


@router.patch("/compliance-policies/{policy_id}")
async def update_compliance_policy(
    request: Request,
    policy_id: str,
    body: UpdateCompliancePolicyRequest,
    store: Annotated[ComplianceStore, Depends(get_compliance_policy_store)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(policy_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Compliance policy not found")
    await dispatch_event(
        request,
        CompliancePolicyUpdated(payload={"resource_id": policy_id}),
        stream_id=f"compliance_policy:{policy_id}",
    )
    return result


@router.delete("/compliance-policies/{policy_id}", status_code=204)
async def remove_compliance_policy(
    request: Request,
    policy_id: str,
    store: Annotated[ComplianceStore, Depends(get_compliance_policy_store)],
) -> None:
    if not await store.remove(policy_id):
        raise HTTPException(status_code=404, detail="Compliance policy not found")
    await dispatch_event(
        request,
        CompliancePolicyRemoved(payload={"resource_id": policy_id}),
        stream_id=f"compliance_policy:{policy_id}",
    )


# ===================== PROCEDURES =====================


class CreateProcedureRequest(BaseModel):
    procedure_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    policy_ids: list[str] = []
    workflow_definition_id: str = ""
    steps: list[str] = []
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.DRAFT
    risk_level: RiskLevel = RiskLevel.MEDIUM
    tags: list[str] = []


class UpdateProcedureRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    policy_ids: list[str] | None = None
    workflow_definition_id: str | None = None
    steps: list[str] | None = None
    owner: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    tags: list[str] | None = None


@router.post("/procedures", status_code=201)
async def create_procedure(
    request: Request,
    body: CreateProcedureRequest,
    store: Annotated[ComplianceStore, Depends(get_procedure_store)],
) -> dict[str, Any]:
    existing = await store.get(body.procedure_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Procedure already exists")
    procedure = Procedure(
        procedure_id=body.procedure_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        policy_ids=tuple(body.policy_ids),
        workflow_definition_id=body.workflow_definition_id,
        steps=tuple(body.steps),
        owner=body.owner,
        status=body.status,
        risk_level=body.risk_level,
        tags=tuple(body.tags),
    )
    result = await store.add(procedure)
    await dispatch_event(
        request,
        ProcedureCreated(payload={"resource_id": body.procedure_id, "name": body.name}),
        stream_id=f"procedure:{body.procedure_id}",
    )
    return result


@router.get("/procedures")
async def list_procedures(
    store: Annotated[ComplianceStore, Depends(get_procedure_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/procedures/{procedure_id}")
async def get_procedure(
    procedure_id: str,
    store: Annotated[ComplianceStore, Depends(get_procedure_store)],
) -> dict[str, Any]:
    item = await store.get(procedure_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Procedure not found")
    return item


@router.patch("/procedures/{procedure_id}")
async def update_procedure(
    request: Request,
    procedure_id: str,
    body: UpdateProcedureRequest,
    store: Annotated[ComplianceStore, Depends(get_procedure_store)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(procedure_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Procedure not found")
    await dispatch_event(
        request,
        ProcedureUpdated(payload={"resource_id": procedure_id}),
        stream_id=f"procedure:{procedure_id}",
    )
    return result


@router.delete("/procedures/{procedure_id}", status_code=204)
async def remove_procedure(
    request: Request,
    procedure_id: str,
    store: Annotated[ComplianceStore, Depends(get_procedure_store)],
) -> None:
    if not await store.remove(procedure_id):
        raise HTTPException(status_code=404, detail="Procedure not found")
    await dispatch_event(
        request,
        ProcedureRemoved(payload={"resource_id": procedure_id}),
        stream_id=f"procedure:{procedure_id}",
    )


# ===================== PRACTICES =====================


class CreatePracticeRequest(BaseModel):
    practice_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    procedure_ids: list[str] = []
    strategy_ids: list[str] = []
    evidence_type: str = ""
    automation_status: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    risk_level: RiskLevel = RiskLevel.LOW
    tags: list[str] = []


class UpdatePracticeRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    procedure_ids: list[str] | None = None
    strategy_ids: list[str] | None = None
    evidence_type: str | None = None
    automation_status: str | None = None
    status: ComplianceStatus | None = None
    risk_level: RiskLevel | None = None
    tags: list[str] | None = None


@router.post("/practices", status_code=201)
async def create_practice(
    request: Request,
    body: CreatePracticeRequest,
    store: Annotated[ComplianceStore, Depends(get_practice_store)],
) -> dict[str, Any]:
    existing = await store.get(body.practice_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Practice already exists")
    practice = Practice(
        practice_id=body.practice_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        procedure_ids=tuple(body.procedure_ids),
        strategy_ids=tuple(body.strategy_ids),
        evidence_type=body.evidence_type,
        automation_status=body.automation_status,
        status=body.status,
        risk_level=body.risk_level,
        tags=tuple(body.tags),
    )
    result = await store.add(practice)
    await dispatch_event(
        request,
        PracticeCreated(payload={"resource_id": body.practice_id, "name": body.name}),
        stream_id=f"practice:{body.practice_id}",
    )
    return result


@router.get("/practices")
async def list_practices(
    store: Annotated[ComplianceStore, Depends(get_practice_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/practices/{practice_id}")
async def get_practice(
    practice_id: str,
    store: Annotated[ComplianceStore, Depends(get_practice_store)],
) -> dict[str, Any]:
    item = await store.get(practice_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    return item


@router.patch("/practices/{practice_id}")
async def update_practice(
    request: Request,
    practice_id: str,
    body: UpdatePracticeRequest,
    store: Annotated[ComplianceStore, Depends(get_practice_store)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(practice_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Practice not found")
    await dispatch_event(
        request,
        PracticeUpdated(payload={"resource_id": practice_id}),
        stream_id=f"practice:{practice_id}",
    )
    return result


@router.delete("/practices/{practice_id}", status_code=204)
async def remove_practice(
    request: Request,
    practice_id: str,
    store: Annotated[ComplianceStore, Depends(get_practice_store)],
) -> None:
    if not await store.remove(practice_id):
        raise HTTPException(status_code=404, detail="Practice not found")
    await dispatch_event(
        request,
        PracticeRemoved(payload={"resource_id": practice_id}),
        stream_id=f"practice:{practice_id}",
    )


# ===================== STRATEGIES =====================


class CreateStrategyRequest(BaseModel):
    strategy_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    description: str = ""
    objectives: list[str] = []
    owner: str = ""
    status: ComplianceStatus = ComplianceStatus.ACTIVE
    tags: list[str] = []


class UpdateStrategyRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    objectives: list[str] | None = None
    owner: str | None = None
    status: ComplianceStatus | None = None
    tags: list[str] | None = None


@router.post("/strategies", status_code=201)
async def create_strategy(
    request: Request,
    body: CreateStrategyRequest,
    store: Annotated[ComplianceStore, Depends(get_strategy_store)],
) -> dict[str, Any]:
    existing = await store.get(body.strategy_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Strategy already exists")
    strategy = Strategy(
        strategy_id=body.strategy_id,
        project_id=body.project_id,
        name=body.name,
        description=body.description,
        objectives=tuple(body.objectives),
        owner=body.owner,
        status=body.status,
        tags=tuple(body.tags),
    )
    result = await store.add(strategy)
    await dispatch_event(
        request,
        StrategyCreated(payload={"resource_id": body.strategy_id, "name": body.name}),
        stream_id=f"strategy:{body.strategy_id}",
    )
    return result


@router.get("/strategies")
async def list_strategies(
    store: Annotated[ComplianceStore, Depends(get_strategy_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/strategies/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    store: Annotated[ComplianceStore, Depends(get_strategy_store)],
) -> dict[str, Any]:
    item = await store.get(strategy_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return item


@router.patch("/strategies/{strategy_id}")
async def update_strategy(
    request: Request,
    strategy_id: str,
    body: UpdateStrategyRequest,
    store: Annotated[ComplianceStore, Depends(get_strategy_store)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(strategy_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Strategy not found")
    await dispatch_event(
        request,
        StrategyUpdated(payload={"resource_id": strategy_id}),
        stream_id=f"strategy:{strategy_id}",
    )
    return result


@router.delete("/strategies/{strategy_id}", status_code=204)
async def remove_strategy(
    request: Request,
    strategy_id: str,
    store: Annotated[ComplianceStore, Depends(get_strategy_store)],
) -> None:
    if not await store.remove(strategy_id):
        raise HTTPException(status_code=404, detail="Strategy not found")
    await dispatch_event(
        request,
        StrategyRemoved(payload={"resource_id": strategy_id}),
        stream_id=f"strategy:{strategy_id}",
    )


# ===================== KNOWLEDGE ENTRIES =====================


class CreateKnowledgeEntryRequest(BaseModel):
    entry_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    name: str
    entry_type: KnowledgeEntryType = KnowledgeEntryType.LOGIC_FLOW
    description: str = ""
    source_file: str = ""
    source_repo: str = ""
    source_lines: str = ""
    dependencies: list[str] = []
    code_snippet: str = ""
    extracted_at: str = ""
    status: ExtractionStatus = ExtractionStatus.COMPLETED
    tags: list[str] = []


class UpdateKnowledgeEntryRequest(BaseModel):
    name: str | None = None
    entry_type: KnowledgeEntryType | None = None
    description: str | None = None
    source_file: str | None = None
    source_repo: str | None = None
    source_lines: str | None = None
    dependencies: list[str] | None = None
    code_snippet: str | None = None
    status: ExtractionStatus | None = None
    tags: list[str] | None = None


@router.post("/knowledge-entries", status_code=201)
async def create_knowledge_entry(
    request: Request,
    body: CreateKnowledgeEntryRequest,
    store: Annotated[ComplianceStore, Depends(get_knowledge_entry_store)],
) -> dict[str, Any]:
    existing = await store.get(body.entry_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Knowledge entry already exists")
    entry = KnowledgeEntry(
        entry_id=body.entry_id,
        project_id=body.project_id,
        name=body.name,
        entry_type=body.entry_type,
        description=body.description,
        source_file=body.source_file,
        source_repo=body.source_repo,
        source_lines=body.source_lines,
        dependencies=tuple(body.dependencies),
        code_snippet=body.code_snippet,
        extracted_at=body.extracted_at,
        status=body.status,
        tags=tuple(body.tags),
    )
    result = await store.add(entry)
    await dispatch_event(
        request,
        KnowledgeEntryCreated(payload={"resource_id": body.entry_id, "name": body.name}),
        stream_id=f"knowledge_entry:{body.entry_id}",
    )
    return result


@router.get("/knowledge-entries")
async def list_knowledge_entries(
    store: Annotated[ComplianceStore, Depends(get_knowledge_entry_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/knowledge-entries/{entry_id}")
async def get_knowledge_entry(
    entry_id: str,
    store: Annotated[ComplianceStore, Depends(get_knowledge_entry_store)],
) -> dict[str, Any]:
    item = await store.get(entry_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return item


@router.patch("/knowledge-entries/{entry_id}")
async def update_knowledge_entry(
    request: Request,
    entry_id: str,
    body: UpdateKnowledgeEntryRequest,
    store: Annotated[ComplianceStore, Depends(get_knowledge_entry_store)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    result = await store.update(entry_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    await dispatch_event(
        request,
        KnowledgeEntryUpdated(payload={"resource_id": entry_id}),
        stream_id=f"knowledge_entry:{entry_id}",
    )
    return result


@router.delete("/knowledge-entries/{entry_id}", status_code=204)
async def remove_knowledge_entry(
    request: Request,
    entry_id: str,
    store: Annotated[ComplianceStore, Depends(get_knowledge_entry_store)],
) -> None:
    if not await store.remove(entry_id):
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    await dispatch_event(
        request,
        KnowledgeEntryRemoved(payload={"resource_id": entry_id}),
        stream_id=f"knowledge_entry:{entry_id}",
    )


# ===================== KNOWLEDGE EXTRACTION RUNS =====================


class CreateKnowledgeExtractionRequest(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    repo_id: str = ""


@router.post("/knowledge-extractions", status_code=201)
async def start_knowledge_extraction(
    request: Request,
    body: CreateKnowledgeExtractionRequest,
    store: Annotated[ComplianceStore, Depends(get_knowledge_extraction_store)],
) -> dict[str, Any]:
    run = KnowledgeExtractionRun(
        run_id=body.run_id,
        project_id=body.project_id,
        repo_id=body.repo_id,
        status=ExtractionStatus.PENDING,
    )
    result = await store.add(run)
    await dispatch_event(
        request,
        KnowledgeExtractionStarted(
            payload={"resource_id": body.run_id, "project_id": body.project_id}
        ),
        stream_id=f"knowledge_extraction:{body.run_id}",
    )
    return result


@router.get("/knowledge-extractions")
async def list_knowledge_extractions(
    store: Annotated[ComplianceStore, Depends(get_knowledge_extraction_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/knowledge-extractions/{run_id}")
async def get_knowledge_extraction(
    run_id: str,
    store: Annotated[ComplianceStore, Depends(get_knowledge_extraction_store)],
) -> dict[str, Any]:
    item = await store.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge extraction run not found")
    return item


# ===================== COMPLIANCE CONFIGURATION =====================


class UpdateComplianceConfigRequest(BaseModel):
    enabled: bool | None = None
    regulations_enabled: bool | None = None
    policies_enabled: bool | None = None
    procedures_enabled: bool | None = None
    practices_enabled: bool | None = None
    strategies_enabled: bool | None = None
    kpis_enabled: bool | None = None
    experiments_enabled: bool | None = None
    metrics_enabled: bool | None = None
    knowledge_base_enabled: bool | None = None


_DEFAULT_CONFIG: dict[str, bool] = {
    "enabled": False,
    "regulations_enabled": True,
    "policies_enabled": True,
    "procedures_enabled": True,
    "practices_enabled": True,
    "strategies_enabled": True,
    "kpis_enabled": True,
    "experiments_enabled": True,
    "metrics_enabled": True,
    "knowledge_base_enabled": True,
}


@router.get("/compliance/config/{project_id}")
async def get_compliance_config(
    project_id: str,
    request: Request,
) -> dict[str, Any]:
    """Get compliance configuration for a project."""
    store = request.app.state.project_store
    project = await store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    config = project.get("compliance_config", dict(_DEFAULT_CONFIG))
    return {"project_id": project_id, **config}


@router.patch("/compliance/config/{project_id}")
async def update_compliance_config(
    project_id: str,
    body: UpdateComplianceConfigRequest,
    request: Request,
) -> dict[str, Any]:
    """Enable/disable compliance features for a project."""
    store = request.app.state.project_store
    project = await store.get(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    current_config = project.get("compliance_config", dict(_DEFAULT_CONFIG))
    updates = body.model_dump(exclude_none=True)
    merged_config = {**current_config, **updates}
    project["compliance_config"] = merged_config
    await store.update(project_id, project)
    await dispatch_event(
        request,
        ProjectUpdated(
            payload={
                "resource_id": project_id,
                "fields": ["compliance_config"],
                "compliance_config": merged_config,
            }
        ),
        stream_id=f"project:{project_id}",
    )
    return {"project_id": project_id, **merged_config}


# ===================== COMPLIANCE OVERVIEW =====================


# ===================== REGULATION TEMPLATES =====================


@router.get("/compliance/regulation-templates")
async def list_regulation_templates() -> list[dict[str, Any]]:
    """List all well-known regulation templates that can be added to projects."""
    from dataclasses import asdict

    from lintel.api.domain.compliance_seed import SEED_REGULATIONS

    results = []
    for reg in SEED_REGULATIONS:
        d = asdict(reg)
        for k, v in d.items():
            if isinstance(v, (tuple, frozenset)):
                d[k] = list(v)
        results.append(d)
    return results


class AddRegulationFromTemplateRequest(BaseModel):
    template_id: str
    project_id: str


@router.post("/compliance/regulation-from-template", status_code=201)
async def add_regulation_from_template(
    request: Request,
    body: AddRegulationFromTemplateRequest,
    store: Annotated[ComplianceStore, Depends(get_regulation_store)],
) -> dict[str, Any]:
    """Add a regulation to a project from a well-known template."""
    from lintel.api.domain.compliance_seed import SEED_REGULATIONS

    template = next((r for r in SEED_REGULATIONS if r.regulation_id == body.template_id), None)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    new_id = f"{body.template_id}-{body.project_id}"
    existing = await store.get(new_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Regulation already added to this project")

    regulation = Regulation(
        regulation_id=new_id,
        project_id=body.project_id,
        name=template.name,
        description=template.description,
        authority=template.authority,
        reference_url=template.reference_url,
        version=template.version,
        status=template.status,
        risk_level=template.risk_level,
        tags=template.tags,
    )
    result = await store.add(regulation)
    await dispatch_event(
        request,
        RegulationCreated(
            payload={"resource_id": new_id, "name": template.name, "template_id": body.template_id}
        ),
        stream_id=f"regulation:{new_id}",
    )
    return result


# ===================== ARCHITECTURE DECISIONS =====================


class CreateArchitectureDecisionRequest(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    project_id: str
    title: str
    status: ADRStatus = ADRStatus.PROPOSED
    context: str = ""
    decision: str = ""
    consequences: str = ""
    alternatives: str = ""
    superseded_by: str = ""
    regulation_ids: list[str] = []
    tags: list[str] = []
    date_proposed: str = ""
    date_decided: str = ""
    deciders: list[str] = []


class UpdateArchitectureDecisionRequest(BaseModel):
    title: str | None = None
    status: ADRStatus | None = None
    context: str | None = None
    decision: str | None = None
    consequences: str | None = None
    alternatives: str | None = None
    superseded_by: str | None = None
    regulation_ids: list[str] | None = None
    tags: list[str] | None = None
    date_proposed: str | None = None
    date_decided: str | None = None
    deciders: list[str] | None = None


@router.post("/architecture-decisions", status_code=201)
async def create_architecture_decision(
    body: CreateArchitectureDecisionRequest,
    request: Request,
    store: Annotated[ComplianceStore, Depends(get_architecture_decision_store)],
) -> dict[str, Any]:
    adr = ArchitectureDecision(
        decision_id=body.decision_id,
        project_id=body.project_id,
        title=body.title,
        status=body.status,
        context=body.context,
        decision=body.decision,
        consequences=body.consequences,
        alternatives=body.alternatives,
        superseded_by=body.superseded_by,
        regulation_ids=tuple(body.regulation_ids),
        tags=tuple(body.tags),
        date_proposed=body.date_proposed,
        date_decided=body.date_decided,
        deciders=tuple(body.deciders),
    )
    existing = await store.get(body.decision_id)
    if existing is not None:
        raise HTTPException(status_code=409, detail="Decision already exists")
    result = await store.add(adr)
    await dispatch_event(
        request,
        ArchitectureDecisionCreated(
            payload={"resource_id": body.decision_id, "title": body.title},
        ),
        stream_id=f"architecture-decision:{body.decision_id}",
    )
    return result


@router.get("/architecture-decisions")
async def list_architecture_decisions(
    store: Annotated[ComplianceStore, Depends(get_architecture_decision_store)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/architecture-decisions/{decision_id}")
async def get_architecture_decision(
    decision_id: str,
    store: Annotated[ComplianceStore, Depends(get_architecture_decision_store)],
) -> dict[str, Any]:
    result = await store.get(decision_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return result


@router.patch("/architecture-decisions/{decision_id}")
async def update_architecture_decision(
    decision_id: str,
    body: UpdateArchitectureDecisionRequest,
    request: Request,
    store: Annotated[ComplianceStore, Depends(get_architecture_decision_store)],
) -> dict[str, Any]:
    updates = body.model_dump(exclude_none=True)
    if "regulation_ids" in updates:
        updates["regulation_ids"] = tuple(updates["regulation_ids"])
    if "tags" in updates:
        updates["tags"] = tuple(updates["tags"])
    if "deciders" in updates:
        updates["deciders"] = tuple(updates["deciders"])
    result = await store.update(decision_id, updates)
    if result is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    await dispatch_event(
        request,
        ArchitectureDecisionUpdated(
            payload={"resource_id": decision_id},
        ),
        stream_id=f"architecture-decision:{decision_id}",
    )
    return result


@router.delete("/architecture-decisions/{decision_id}", status_code=204)
async def delete_architecture_decision(
    decision_id: str,
    request: Request,
    store: Annotated[ComplianceStore, Depends(get_architecture_decision_store)],
) -> None:
    removed = await store.remove(decision_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Decision not found")
    await dispatch_event(
        request,
        ArchitectureDecisionRemoved(
            payload={"resource_id": decision_id},
        ),
        stream_id=f"architecture-decision:{decision_id}",
    )


@router.get("/compliance/overview/{project_id}")
async def compliance_overview(
    project_id: str,
    request: Request,
) -> dict[str, Any]:
    """Aggregated compliance governance overview for a project."""
    reg_store: ComplianceStore = request.app.state.regulation_store
    pol_store: ComplianceStore = request.app.state.compliance_policy_store
    proc_store: ComplianceStore = request.app.state.procedure_store
    prac_store: ComplianceStore = request.app.state.practice_store
    strat_store: ComplianceStore = request.app.state.strategy_store
    kpi_store: ComplianceStore = request.app.state.kpi_store
    exp_store: ComplianceStore = request.app.state.experiment_store
    met_store: ComplianceStore = request.app.state.compliance_metric_store
    kb_store: ComplianceStore = request.app.state.knowledge_entry_store
    adr_store: ComplianceStore = request.app.state.architecture_decision_store

    regulations = await reg_store.list_by_project(project_id)
    policies = await pol_store.list_by_project(project_id)
    procedures = await proc_store.list_by_project(project_id)
    practices = await prac_store.list_by_project(project_id)
    strategies = await strat_store.list_by_project(project_id)
    kpis = await kpi_store.list_by_project(project_id)
    experiments = await exp_store.list_by_project(project_id)
    metrics = await met_store.list_by_project(project_id)
    knowledge = await kb_store.list_by_project(project_id)
    adrs = await adr_store.list_by_project(project_id)

    # Compute risk distribution
    all_items = regulations + policies + procedures + practices
    risk_counts: dict[str, int] = {}
    for item in all_items:
        rl = item.get("risk_level", "medium")
        risk_counts[rl] = risk_counts.get(rl, 0) + 1

    # Compute status distribution
    status_counts: dict[str, int] = {}
    for item in all_items:
        st = item.get("status", "draft")
        status_counts[st] = status_counts.get(st, 0) + 1

    return {
        "project_id": project_id,
        "counts": {
            "regulations": len(regulations),
            "policies": len(policies),
            "procedures": len(procedures),
            "practices": len(practices),
            "strategies": len(strategies),
            "kpis": len(kpis),
            "experiments": len(experiments),
            "metrics": len(metrics),
            "knowledge_entries": len(knowledge),
            "architecture_decisions": len(adrs),
        },
        "risk_distribution": risk_counts,
        "status_distribution": status_counts,
        "cascade": {
            "regulations": regulations,
            "policies": policies,
            "procedures": procedures,
            "practices": practices,
        },
        "strategies": strategies,
        "kpis": kpis,
        "architecture_decisions": adrs,
    }
