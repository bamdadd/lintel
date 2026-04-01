"""Authentication domain types — User identity, tokens, and roles."""

from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from datetime import datetime
    from uuid import UUID


class UserRole(StrEnum):
    """Authentication roles for access control."""

    MEMBER = "member"
    ADMIN = "admin"
    SUPERUSER = "superuser"


class AuthUser(BaseModel, frozen=True):
    """Authenticated user identity stored in the users table."""

    id: UUID
    email: str
    display_name: str
    role: UserRole
    hashed_password: str
    created_at: datetime
    updated_at: datetime | None = None


class TokenPair(BaseModel, frozen=True):
    """JWT access + refresh token pair returned on login/refresh."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
