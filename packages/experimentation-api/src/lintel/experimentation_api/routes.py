"""Experimentation endpoints — barrel module."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.experimentation_api.evolutionary_strategies import (
    evo_strategy_store_provider,
)
from lintel.experimentation_api.evolutionary_strategies import (
    router as evo_strategies_router,
)
from lintel.experimentation_api.experiments import (
    CreateExperimentRequest,
    UpdateExperimentRequest,
    experiment_store_provider,
)
from lintel.experimentation_api.experiments import (
    router as experiments_router,
)
from lintel.experimentation_api.kpi_linkage import (
    kpi_mapping_store_provider,
)
from lintel.experimentation_api.kpi_linkage import (
    router as kpi_linkage_router,
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
from lintel.experimentation_api.run_metrics import (
    router as run_metrics_router,
)
from lintel.experimentation_api.run_metrics import (
    run_metric_store_provider,
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
    "evo_strategy_store_provider",
    "experiment_store_provider",
    "kpi_mapping_store_provider",
    "kpi_store_provider",
    "router",
    "run_metric_store_provider",
]

router = APIRouter()
router.include_router(kpis_router)
router.include_router(experiments_router)
router.include_router(metrics_router)
router.include_router(run_metrics_router)
router.include_router(evo_strategies_router)
router.include_router(kpi_linkage_router)
