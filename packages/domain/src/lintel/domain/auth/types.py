"""Auth domain types."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class AuthRole(StrEnum):
    """Role for authentication / authorization."""

    MEMBER = "member"
    ADMIN = "admin"
    SUPERUSER = "superuser"


@dataclass(frozen=True)
class AuthUser:
    """User with authentication credentials.

    Extends the concept of the domain ``User`` with a hashed password and
    an auth-specific role.
    """

    user_id: str
    email: str
    name: str
    hashed_password: str
    role: AuthRole = AuthRole.MEMBER
