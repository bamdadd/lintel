"""Encryption management REST endpoints."""

from __future__ import annotations

from dataclasses import asdict
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends

from lintel.api_support.provider import StoreProvider

if TYPE_CHECKING:
    from lintel.encryption_api.store import EncryptionStore

router = APIRouter()

encryption_store_provider: StoreProvider[EncryptionStore] = StoreProvider()


@router.post("/encryption/keys", status_code=201)
async def rotate_key(
    store: EncryptionStore = Depends(encryption_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Generate a new encryption key and mark it active."""
    meta = store.encryptor.rotate_key()
    return asdict(meta)


@router.get("/encryption/status")
async def encryption_status(
    store: EncryptionStore = Depends(encryption_store_provider),  # noqa: B008
) -> dict[str, Any]:
    """Return current encryption key status."""
    return store.encryptor.status()
