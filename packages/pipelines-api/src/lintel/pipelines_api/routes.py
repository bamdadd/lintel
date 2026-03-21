"""Barrel file — aggregates all pipeline sub-routers and re-exports store symbols."""

from fastapi import APIRouter

from lintel.pipelines_api import events, interrupts, pipelines, stages
from lintel.pipelines_api._store import InMemoryPipelineStore, pipeline_store_provider
from lintel.pipelines_api.interrupts import interrupt_store_provider

__all__ = [
    "InMemoryPipelineStore",
    "interrupt_store_provider",
    "pipeline_store_provider",
    "router",
]

router = APIRouter()
router.include_router(pipelines.router)
router.include_router(stages.router)
router.include_router(events.router)
router.include_router(interrupts.router)
