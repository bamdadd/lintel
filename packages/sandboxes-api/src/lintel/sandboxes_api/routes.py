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
from lintel.sandboxes_api.sub_sessions import (
    router as sub_sessions_router,
)
from lintel.sandboxes_api.sub_sessions import (
    sub_session_store_provider,
)

# Re-export sub-module symbols for backward compatibility
__all__ = [
    "SANDBOX_PRESETS",
    "CreateSandboxRequest",
    "DevcontainerConfig",
    "DevcontainerFeature",
    "MountConfig",
    "SandboxStore",
    "router",
    "sub_session_store_provider",
]

router = APIRouter()
# Sub-sessions routes first (before parameterized /sandboxes/{sandbox_id})
router.include_router(sub_sessions_router)
router.include_router(sandboxes_router)
router.include_router(execution_router)
router.include_router(files_router)
