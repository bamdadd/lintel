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
    router as sandboxes_router,
)

# Re-export sub-module symbols for backward compatibility
__all__ = [
    "router",
    "SandboxStore",
    "SANDBOX_PRESETS",
    "CreateSandboxRequest",
    "DevcontainerConfig",
    "DevcontainerFeature",
    "MountConfig",
]

router = APIRouter()
router.include_router(sandboxes_router)
router.include_router(execution_router)
router.include_router(files_router)
