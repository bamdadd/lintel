"""Tests for sandbox domain exceptions."""

from __future__ import annotations

from lintel.contracts.errors import (
    SandboxError,
    SandboxExecutionError,
    SandboxNotFoundError,
    SandboxTimeoutError,
)
import pytest


class TestSandboxError:
    def test_base_error_catchable(self) -> None:
        with pytest.raises(SandboxError):
            raise SandboxError("something went wrong")


class TestSandboxNotFoundError:
    def test_exposes_sandbox_id(self) -> None:
        exc = SandboxNotFoundError("abc-123")
        assert exc.sandbox_id == "abc-123"

    def test_message_includes_id(self) -> None:
        exc = SandboxNotFoundError("abc-123")
        assert "abc-123" in str(exc)

    def test_is_sandbox_error(self) -> None:
        with pytest.raises(SandboxError):
            raise SandboxNotFoundError("x")


class TestSandboxTimeoutError:
    def test_is_sandbox_error(self) -> None:
        with pytest.raises(SandboxError):
            raise SandboxTimeoutError("timed out")


class TestSandboxExecutionError:
    def test_is_sandbox_error(self) -> None:
        with pytest.raises(SandboxError):
            raise SandboxExecutionError("exec failed")
