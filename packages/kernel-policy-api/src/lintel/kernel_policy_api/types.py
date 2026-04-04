"""Kernel policy domain types."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class KernelPolicyType(StrEnum):
    """Type of kernel-level enforcement policy."""

    SECCOMP = "seccomp"
    APPARMOR = "apparmor"


class KernelPolicyStatus(StrEnum):
    """Lifecycle status of a kernel policy."""

    DRAFT = "draft"
    ACTIVE = "active"
    APPLIED = "applied"


@dataclass(frozen=True)
class KernelPolicy:
    """A kernel-level security policy (seccomp/apparmor) for sandbox enforcement."""

    policy_id: str
    name: str
    policy_type: KernelPolicyType
    description: str = ""
    rules: dict[str, object] = field(default_factory=dict)
    status: KernelPolicyStatus = KernelPolicyStatus.DRAFT
    project_id: str = ""
