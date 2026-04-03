"""Sandbox management endpoints — barrel module."""

from __future__ import annotations

from fastapi import APIRouter

from lintel.sandboxes_api.execution import router as execution_router
from lintel.sandboxes_api.files import router as files_router
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
from lintel.sandboxes_api.snapshot_store import InMemorySnapshotStore
from lintel.sandboxes_api.snapshots import router as snapshots_router
from lintel.sandboxes_api.snapshots import snapshot_store_provider

# Re-export sub-module symbols for backward compatibility
__all__ = [
    "SANDBOX_PRESETS",
    "CreateSandboxRequest",
    "DevcontainerConfig",
    "DevcontainerFeature",
    "InMemorySnapshotStore",
    "MountConfig",
    "SandboxStore",
    "router",
    "snapshot_store_provider",
]

router = APIRouter()
router.include_router(snapshots_router)
router.include_router(sandboxes_router)
router.include_router(execution_router)
router.include_router(files_router)
