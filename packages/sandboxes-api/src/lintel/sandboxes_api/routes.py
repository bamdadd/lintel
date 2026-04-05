"""Sandbox management endpoints — barrel module."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.sandboxes_api.execution import router as execution_router
from lintel.sandboxes_api.files import router as files_router
from lintel.sandboxes_api.preview import router as preview_router
from lintel.sandboxes_api.replica_store import DatabaseReplicaConfig, InMemoryReplicaConfigStore
from lintel.sandboxes_api.replicas import replica_config_store_provider
from lintel.sandboxes_api.replicas import router as replicas_router
from lintel.sandboxes_api.sandboxes import (
    SANDBOX_PRESETS,
    CreateSandboxRequest,
    DevcontainerConfig,
    DevcontainerFeature,
    MountConfig,
    SandboxStore,
)
from lintel.sandboxes_api.sandboxes import (
    router as sandboxes_router,
)
from lintel.sandboxes_api.session_lifecycle import lifecycle_manager_provider
from lintel.sandboxes_api.session_lifecycle import router as session_lifecycle_router
from lintel.sandboxes_api.snapshot_store import InMemorySnapshotStore
from lintel.sandboxes_api.snapshots import router as snapshots_router
from lintel.sandboxes_api.snapshots import snapshot_store_provider

# Re-export sub-module symbols for backward compatibility
__all__ = [
    "SANDBOX_PRESETS",
    "CreateSandboxRequest",
    "DatabaseReplicaConfig",
    "DevcontainerConfig",
    "DevcontainerFeature",
    "InMemoryReplicaConfigStore",
    "InMemorySnapshotStore",
    "MountConfig",
    "SandboxStore",
    "lifecycle_manager_provider",
    "replica_config_store_provider",
    "router",
    "snapshot_store_provider",
]

router = APIRouter()
router.include_router(session_lifecycle_router)
router.include_router(snapshots_router)
router.include_router(sandboxes_router)
router.include_router(execution_router)
router.include_router(files_router)
router.include_router(preview_router)
router.include_router(replicas_router)
