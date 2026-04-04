"""Fernet-based field-level encryptor service."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime
import logging
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

ENCRYPTED_PREFIX = "enc:v1:"


@dataclass
class KeyMetadata:
    """Metadata for an encryption key."""

    key_id: str
    created_at: str
    active: bool = True


@dataclass
class FieldEncryptor:
    """Encrypts and decrypts marked fields using Fernet symmetric encryption.

    The active key is used for all new encryptions.  Previous keys are kept
    for decryption during key-rotation windows.

    The environment variable ``LINTEL_ENCRYPTION_KEY`` seeds the initial key.
    If absent a random key is generated (suitable for dev/test).
    """

    _keys: dict[str, bytes] = field(default_factory=dict)
    _metadata: list[KeyMetadata] = field(default_factory=list)
    _active_key_id: str = ""

    def __post_init__(self) -> None:
        if not self._keys:
            env_key = os.environ.get("LINTEL_ENCRYPTION_KEY")
            raw = env_key.encode() if env_key else Fernet.generate_key()
            self._bootstrap_key(raw)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string, returning a prefixed ciphertext."""
        f = Fernet(self._keys[self._active_key_id])
        token = f.encrypt(plaintext.encode()).decode()
        return f"{ENCRYPTED_PREFIX}{self._active_key_id}:{token}"

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a prefixed ciphertext string."""
        if not ciphertext.startswith(ENCRYPTED_PREFIX):
            return ciphertext
        rest = ciphertext[len(ENCRYPTED_PREFIX) :]
        key_id, _, token = rest.partition(":")
        if not token or key_id not in self._keys:
            msg = f"Unknown encryption key: {key_id}"
            raise InvalidToken(msg)
        f = Fernet(self._keys[key_id])
        return f.decrypt(token.encode()).decode()

    def encrypt_fields(self, data: dict[str, Any], field_names: set[str]) -> dict[str, Any]:
        """Return a copy of *data* with specified fields encrypted."""
        out = dict(data)
        for name in field_names:
            val = out.get(name)
            if isinstance(val, str) and not val.startswith(ENCRYPTED_PREFIX):
                out[name] = self.encrypt(val)
        return out

    def decrypt_fields(self, data: dict[str, Any], field_names: set[str]) -> dict[str, Any]:
        """Return a copy of *data* with specified fields decrypted."""
        out = dict(data)
        for name in field_names:
            val = out.get(name)
            if isinstance(val, str) and val.startswith(ENCRYPTED_PREFIX):
                out[name] = self.decrypt(val)
        return out

    def rotate_key(self) -> KeyMetadata:
        """Generate a new key, mark it active, and keep old keys for decryption."""
        new_raw = Fernet.generate_key()
        return self._bootstrap_key(new_raw, deactivate_previous=True)

    def status(self) -> dict[str, Any]:
        """Return current encryption status."""
        return {
            "active_key_id": self._active_key_id,
            "total_keys": len(self._keys),
            "keys": [
                {"key_id": m.key_id, "created_at": m.created_at, "active": m.active}
                for m in self._metadata
            ],
        }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _bootstrap_key(
        self,
        raw_key: bytes,
        *,
        deactivate_previous: bool = False,
    ) -> KeyMetadata:
        key_id = base64.urlsafe_b64encode(raw_key[:6]).decode().rstrip("=")
        self._keys[key_id] = raw_key
        if deactivate_previous:
            for m in self._metadata:
                m.active = False
        meta = KeyMetadata(
            key_id=key_id,
            created_at=datetime.now(UTC).isoformat(),
            active=True,
        )
        self._metadata.append(meta)
        self._active_key_id = key_id
        logger.info("encryption_key_registered", extra={"key_id": key_id})
        return meta
