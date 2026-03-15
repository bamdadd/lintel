"""Experimentation endpoints — barrel module."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.experimentation_api.experiments import (
    CreateExperimentRequest,
    UpdateExperimentRequest,
    experiment_store_provider,
    router as experiments_router,
)
from lintel.experimentation_api.kpis import (
    CreateKPIRequest,
    UpdateKPIRequest,
    kpi_store_provider,
    router as kpis_router,
)
from lintel.experimentation_api.metrics import (
    CreateComplianceMetricRequest,
    UpdateComplianceMetricRequest,
    compliance_metric_store_provider,
    router as metrics_router,
)

# Re-export for backward compatibility
__all__ = [
    "router",
    "kpi_store_provider",
    "experiment_store_provider",
    "compliance_metric_store_provider",
    "CreateKPIRequest",
    "UpdateKPIRequest",
    "CreateExperimentRequest",
    "UpdateExperimentRequest",
    "CreateComplianceMetricRequest",
    "UpdateComplianceMetricRequest",
]

router = APIRouter()
router.include_router(kpis_router)
router.include_router(experiments_router)
router.include_router(metrics_router)
