"""Knowledge entry CRUD and knowledge extraction run endpoints."""

from typing import Annotated, Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from lintel.api_support.event_dispatcher import dispatch_event
from lintel.api_support.provider import StoreProvider
from lintel.compliance_api.store import ComplianceStore
from lintel.domain.events import (
    KnowledgeEntryCreated,
    KnowledgeEntryRemoved,
    KnowledgeEntryUpdated,
    KnowledgeExtractionStarted,
)
from lintel.domain.types import (
    ExtractionStatus,
    KnowledgeEntry,
    KnowledgeEntryType,
    KnowledgeExtractionRun,
)

router = APIRouter()

knowledge_entry_store_provider: StoreProvider[ComplianceStore] = StoreProvider()
knowledge_extraction_store_provider: StoreProvider[ComplianceStore] = StoreProvider()


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
    store: Annotated[ComplianceStore, Depends(knowledge_entry_store_provider)],
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
    store: Annotated[ComplianceStore, Depends(knowledge_entry_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/knowledge-entries/{entry_id}")
async def get_knowledge_entry(
    entry_id: str,
    store: Annotated[ComplianceStore, Depends(knowledge_entry_store_provider)],
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
    store: Annotated[ComplianceStore, Depends(knowledge_entry_store_provider)],
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
    store: Annotated[ComplianceStore, Depends(knowledge_entry_store_provider)],
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
    store: Annotated[ComplianceStore, Depends(knowledge_extraction_store_provider)],
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
    store: Annotated[ComplianceStore, Depends(knowledge_extraction_store_provider)],
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    if project_id:
        return await store.list_by_project(project_id)
    return await store.list_all()


@router.get("/knowledge-extractions/{run_id}")
async def get_knowledge_extraction(
    run_id: str,
    store: Annotated[ComplianceStore, Depends(knowledge_extraction_store_provider)],
) -> dict[str, Any]:
    item = await store.get(run_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Knowledge extraction run not found")
    return item
