"""Integrations domain: ticketing adapters, external system connectors, and observability bridge."""

from lintel.domain.integrations.board_sync import (
    BoardSyncConfig,
    BoardSyncEngine,
    ExternalBoardProvider,
    ExternalWorkItem,
    SyncDiff,
    SyncDirection,
)
from lintel.domain.integrations.observability import (
    Alert,
    AlertSeverity,
    MetricExport,
    ObservabilityBridge,
    ObservabilityProvider,
)

__all__ = [
    "Alert",
    "AlertSeverity",
    "BoardSyncConfig",
    "BoardSyncEngine",
    "ExternalBoardProvider",
    "ExternalWorkItem",
    "MetricExport",
    "ObservabilityBridge",
    "ObservabilityProvider",
    "SyncDiff",
    "SyncDirection",
]
