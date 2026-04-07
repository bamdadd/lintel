"""Tests for sandbox resource guard and hardening helpers."""

from __future__ import annotations

import pytest

from lintel.sandbox.errors import FileWriteLimitExceededError, ToolCallLimitExceededError
from lintel.sandbox.resource_guard import (
    ResourceGuard,
    build_egress_iptables_script,
    build_security_opt,
    build_storage_opt,
)
from lintel.sandbox.types import NetworkEgressPolicy, ResourceLimits, ToolCallLimits


class TestResourceGuard:
    def test_tool_call_within_limit(self) -> None:
        guard = ResourceGuard(ToolCallLimits(max_tool_calls_per_step=3))
        guard.record_tool_call()
        guard.record_tool_call()
        guard.record_tool_call()
        assert guard.tool_calls == 3

    def test_tool_call_exceeds_limit(self) -> None:
        guard = ResourceGuard(ToolCallLimits(max_tool_calls_per_step=2))
        guard.record_tool_call()
        guard.record_tool_call()
        with pytest.raises(ToolCallLimitExceededError):
            guard.record_tool_call()

    def test_file_write_within_limit(self) -> None:
        guard = ResourceGuard(ToolCallLimits(max_file_writes_per_session=2))
        guard.record_file_write()
        guard.record_file_write()
        assert guard.file_writes == 2

    def test_file_write_exceeds_limit(self) -> None:
        guard = ResourceGuard(ToolCallLimits(max_file_writes_per_session=1))
        guard.record_file_write()
        with pytest.raises(FileWriteLimitExceededError):
            guard.record_file_write()

    def test_reset_tool_calls(self) -> None:
        guard = ResourceGuard(ToolCallLimits(max_tool_calls_per_step=2))
        guard.record_tool_call()
        guard.record_tool_call()
        guard.reset_tool_calls()
        # Should succeed again after reset
        guard.record_tool_call()
        assert guard.tool_calls == 1


class TestBuildStorageOpt:
    def test_default_limits(self) -> None:
        result = build_storage_opt(ResourceLimits())
        assert result == {"size": "1024m"}

    def test_custom_disk(self) -> None:
        result = build_storage_opt(ResourceLimits(max_disk_mb=2048))
        assert result == {"size": "2048m"}


class TestBuildSecurityOpt:
    def test_default_seccomp(self) -> None:
        result = build_security_opt(ResourceLimits())
        assert result == ["no-new-privileges:true"]

    def test_custom_seccomp(self) -> None:
        result = build_security_opt(ResourceLimits(seccomp_profile="/path/to/profile.json"))
        assert result == ["no-new-privileges:true", "seccomp=/path/to/profile.json"]


class TestBuildEgressIptablesScript:
    def test_empty_domains_returns_empty(self) -> None:
        policy = NetworkEgressPolicy()
        assert build_egress_iptables_script(policy) == ""

    def test_with_domains_generates_script(self) -> None:
        policy = NetworkEgressPolicy(allowed_domains=("github.com", "pypi.org"))
        script = build_egress_iptables_script(policy)
        assert "iptables" in script
        assert "github.com" in script
        assert "pypi.org" in script
        assert "DROP" in script
        # DNS must be allowed
        assert "--dport 53" in script

    def test_loopback_allowed(self) -> None:
        policy = NetworkEgressPolicy(allowed_domains=("example.com",))
        script = build_egress_iptables_script(policy)
        assert "-o lo -j ACCEPT" in script


class TestSandboxConfigDefaults:
    def test_new_fields_have_defaults(self) -> None:
        from lintel.sandbox.types import SandboxConfig

        config = SandboxConfig()
        assert config.resource_limits.max_disk_mb == 1024
        assert config.resource_limits.max_processes == 256
        assert config.resource_limits.seccomp_profile == "default"
        assert config.network_egress.allowed_domains == ()
        assert config.tool_limits.max_tool_calls_per_step == 50
        assert config.tool_limits.max_file_writes_per_session == 100
