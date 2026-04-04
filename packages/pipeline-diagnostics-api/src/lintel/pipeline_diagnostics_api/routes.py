"""Pipeline diagnostics endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.pipeline_diagnostics_api.store import InMemoryPipelineDiagnosticStore

router = APIRouter()

diagnostic_store_provider: StoreProvider[InMemoryPipelineDiagnosticStore] = StoreProvider()


# --- Request models ---


class RecordDiagnosticRequest(BaseModel):
    diagnostic_id: str | None = None
    pipeline_run_id: str
    project_id: str = ""
    work_item_id: str = ""
    failed_stage: str
    error_message: str
    error_traceback: str = ""
    category: str = "unknown"
    context: dict[str, object] = Field(default_factory=dict)


# --- Endpoints ---


@router.get("/pipelines/diagnostics")
async def list_diagnostics(
    project_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    store = diagnostic_store_provider.get()
    items = await store.list_all(project_id=project_id, limit=limit)
    return [asdict(d) for d in items]


@router.get("/pipelines/diagnostics/{diagnostic_id}")
async def get_diagnostic(diagnostic_id: str) -> dict[str, Any]:
    store = diagnostic_store_provider.get()
    item = await store.get(diagnostic_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Diagnostic not found")
    return asdict(item)


@router.post("/pipelines/diagnostics", status_code=201)
async def record_diagnostic(body: RecordDiagnosticRequest) -> dict[str, Any]:
    from lintel.pipeline_diagnostics_api.store import PipelineDiagnostic

    store = diagnostic_store_provider.get()
    kwargs: dict[str, Any] = body.model_dump()
    if kwargs["diagnostic_id"] is None:
        del kwargs["diagnostic_id"]
    diagnostic = PipelineDiagnostic(**kwargs)
    try:
        await store.add(diagnostic)
    except ValueError:
        raise HTTPException(status_code=409, detail="Diagnostic already exists")  # noqa: B904
    return asdict(diagnostic)
