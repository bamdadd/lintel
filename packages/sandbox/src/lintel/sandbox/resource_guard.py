"""Resource guard: tracks and enforces per-session sandbox limits.

This module provides ``ResourceGuard`` which tracks tool calls and file writes
per sandbox session, raising limit errors when thresholds are exceeded.  It also
provides helpers used by the Docker backend to apply resource and network
egress constraints at container creation time.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from lintel.sandbox.errors import FileWriteLimitExceededError, ToolCallLimitExceededError

if TYPE_CHECKING:
    from lintel.sandbox.types import (
        NetworkEgressPolicy,
        NetworkPolicy,
        ResourceLimits,
        ToolCallLimits,
    )


class ResourceGuard:
    """Tracks per-session tool call and file write counts, enforcing limits."""

    def __init__(self, limits: ToolCallLimits) -> None:
        self._limits = limits
        self._tool_calls: int = 0
        self._file_writes: int = 0

    @property
    def tool_calls(self) -> int:
        return self._tool_calls

    @property
    def file_writes(self) -> int:
        return self._file_writes

    def record_tool_call(self) -> None:
        """Record a tool call, raising if the per-step limit is exceeded."""
        self._tool_calls += 1
        if self._tool_calls > self._limits.max_tool_calls_per_step:
            raise ToolCallLimitExceededError(self._limits.max_tool_calls_per_step)

    def record_file_write(self) -> None:
        """Record a file write, raising if the session limit is exceeded."""
        self._file_writes += 1
        if self._file_writes > self._limits.max_file_writes_per_session:
            raise FileWriteLimitExceededError(self._limits.max_file_writes_per_session)

    def reset_tool_calls(self) -> None:
        """Reset the per-step tool call counter (called between steps)."""
        self._tool_calls = 0


def build_storage_opt(resource_limits: ResourceLimits) -> dict[str, str]:
    """Return Docker ``storage_opt`` dict for disk quota enforcement.

    Note: disk quotas via ``storage_opt`` require the ``overlay2`` driver with
    ``xfs`` and ``pquota`` mount option.  On systems that don't support this the
    option is silently ignored by Docker.
    """
    return {"size": f"{resource_limits.max_disk_mb}m"}


def build_security_opt(resource_limits: ResourceLimits) -> list[str]:
    """Return Docker ``security_opt`` list including seccomp profile."""
    opts = ["no-new-privileges:true"]
    if resource_limits.seccomp_profile != "default":
        opts.append(f"seccomp={resource_limits.seccomp_profile}")
    return opts


def build_egress_iptables_script(policy: NetworkEgressPolicy) -> str:
    """Return a shell script that restricts egress to allowed domains only.

    The script resolves each allowed domain to its IP addresses, then sets
    iptables OUTPUT rules to allow only those IPs plus DNS (udp/53).
    Everything else is dropped.

    Returns an empty string when no domain restrictions are configured.
    """
    if not policy.allowed_domains:
        return ""

    lines = [
        "#!/bin/sh",
        "set -e",
        # Flush existing OUTPUT rules
        "iptables -F OUTPUT 2>/dev/null || true",
        # Allow loopback
        "iptables -A OUTPUT -o lo -j ACCEPT",
        # Allow DNS so domain resolution works
        "iptables -A OUTPUT -p udp --dport 53 -j ACCEPT",
        "iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT",
        # Allow established/related connections
        "iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
    ]

    for domain in policy.allowed_domains:
        # Resolve each domain and allow its IPs
        lines.append(f"for ip in $(getent hosts {domain} | awk '{{print $1}}'); do")
        lines.append("  iptables -A OUTPUT -d $ip -j ACCEPT")
        lines.append("done")

    # Drop everything else
    lines.append("iptables -A OUTPUT -j DROP")
    return "\n".join(lines)


def build_network_policy_script(policy: NetworkPolicy) -> str:
    """Return a shell script that restricts egress per ``NetworkPolicy``.

    Each ``NetworkEndpoint`` is resolved (via ``getent hosts``) and allowed
    at the specified port/protocol.  When no endpoints are configured the
    function returns an empty string (no restrictions applied).
    """
    if not policy.allowed_endpoints:
        return ""

    lines = [
        "#!/bin/sh",
        "set -e",
        "iptables -F OUTPUT 2>/dev/null || true",
        "iptables -A OUTPUT -o lo -j ACCEPT",
        # Allow DNS
        "iptables -A OUTPUT -p udp --dport 53 -j ACCEPT",
        "iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT",
        "iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT",
    ]

    for ep in policy.allowed_endpoints:
        port_flag = f" --dport {ep.port}" if ep.port is not None else ""
        lines.append(f"for ip in $(getent hosts {ep.host} | awk '{{print $1}}'); do")
        lines.append(f"  iptables -A OUTPUT -p {ep.protocol} -d $ip{port_flag} -j ACCEPT")
        lines.append("done")

    lines.append("iptables -A OUTPUT -j DROP")
    return "\n".join(lines)
