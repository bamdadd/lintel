"""Experimentation endpoints — barrel module."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.experimentation_api.experiments import (
    CreateExperimentRequest,
    UpdateExperimentRequest,
    experiment_store_provider,
)
from lintel.experimentation_api.experiments import (
    router as experiments_router,
)
from lintel.experimentation_api.kpis import (
    CreateKPIRequest,
    UpdateKPIRequest,
    kpi_store_provider,
)
from lintel.experimentation_api.kpis import (
    router as kpis_router,
)
from lintel.experimentation_api.metrics import (
    CreateComplianceMetricRequest,
    UpdateComplianceMetricRequest,
    compliance_metric_store_provider,
)
from lintel.experimentation_api.metrics import (
    router as metrics_router,
)

# Re-export for backward compatibility
__all__ = [
    "CreateComplianceMetricRequest",
    "CreateExperimentRequest",
    "CreateKPIRequest",
    "UpdateComplianceMetricRequest",
    "UpdateExperimentRequest",
    "UpdateKPIRequest",
    "compliance_metric_store_provider",
    "experiment_store_provider",
    "kpi_store_provider",
    "router",
]

router = APIRouter()
router.include_router(kpis_router)
router.include_router(experiments_router)
router.include_router(metrics_router)
