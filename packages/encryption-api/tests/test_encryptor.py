"""Tests for FieldEncryptor."""

from __future__ import annotations

from cryptography.fernet import InvalidToken
import pytest

from lintel.encryption_api.encryptor import ENCRYPTED_PREFIX, FieldEncryptor


class TestEncryptDecrypt:
    def test_roundtrip(self) -> None:
        enc = FieldEncryptor()
        ct = enc.encrypt("hello world")
        assert ct.startswith(ENCRYPTED_PREFIX)
        assert enc.decrypt(ct) == "hello world"

    def test_decrypt_plaintext_passthrough(self) -> None:
        enc = FieldEncryptor()
        assert enc.decrypt("not encrypted") == "not encrypted"

    def test_decrypt_unknown_key_raises(self) -> None:
        enc = FieldEncryptor()
        with pytest.raises(InvalidToken):
            enc.decrypt(f"{ENCRYPTED_PREFIX}badkey:badtoken")


class TestFieldHelpers:
    def test_encrypt_fields(self) -> None:
        enc = FieldEncryptor()
        data = {"name": "alice", "api_token": "secret123", "count": 42}
        result = enc.encrypt_fields(data, {"api_token"})
        assert result["name"] == "alice"
        assert result["api_token"].startswith(ENCRYPTED_PREFIX)
        assert result["count"] == 42

    def test_decrypt_fields(self) -> None:
        enc = FieldEncryptor()
        data = {"api_token": enc.encrypt("secret123"), "name": "alice"}
        result = enc.decrypt_fields(data, {"api_token"})
        assert result["api_token"] == "secret123"
        assert result["name"] == "alice"

    def test_already_encrypted_skipped(self) -> None:
        enc = FieldEncryptor()
        ct = enc.encrypt("secret")
        data = {"token": ct}
        result = enc.encrypt_fields(data, {"token"})
        assert result["token"] == ct  # not double-encrypted


class TestKeyRotation:
    def test_rotate_creates_new_active_key(self) -> None:
        enc = FieldEncryptor()
        old_id = enc._active_key_id
        meta = enc.rotate_key()
        assert meta.active is True
        assert meta.key_id != old_id
        assert enc._active_key_id == meta.key_id

    def test_old_ciphertext_still_decryptable(self) -> None:
        enc = FieldEncryptor()
        ct = enc.encrypt("before rotation")
        enc.rotate_key()
        assert enc.decrypt(ct) == "before rotation"

    def test_new_ciphertext_uses_new_key(self) -> None:
        enc = FieldEncryptor()
        enc.rotate_key()
        new_id = enc._active_key_id
        ct = enc.encrypt("after rotation")
        assert f"{ENCRYPTED_PREFIX}{new_id}:" in ct

    def test_status_after_rotation(self) -> None:
        enc = FieldEncryptor()
        enc.rotate_key()
        status = enc.status()
        assert status["total_keys"] == 2
        active = [k for k in status["keys"] if k["active"]]
        assert len(active) == 1


class TestEnvKey:
    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key()
        monkeypatch.setenv("LINTEL_ENCRYPTION_KEY", key.decode())
        enc = FieldEncryptor()
        ct = enc.encrypt("test")
        assert enc.decrypt(ct) == "test"
