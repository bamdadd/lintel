"""In-memory store for encryption key metadata."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lintel.encryption_api.encryptor import FieldEncryptor


class EncryptionStore:
    """Holds the singleton FieldEncryptor instance for DI wiring."""

    def __init__(self, encryptor: FieldEncryptor | None = None) -> None:
        if encryptor is None:
            from lintel.encryption_api import encryptor as _enc_mod

            encryptor = _enc_mod.FieldEncryptor()
        self._encryptor = encryptor

    @property
    def encryptor(self) -> FieldEncryptor:
        return self._encryptor
