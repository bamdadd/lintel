"""JWT token generation and validation."""

from __future__ import annotations

from dataclasses import dataclass
import os
import time
from typing import Any

import jwt

# Configurable via environment; safe dev default.
JWT_SECRET: str = os.environ.get("JWT_SECRET", "lintel-dev-secret-change-me-at-least-32b")
JWT_ALGORITHM: str = "HS256"
ACCESS_TOKEN_EXPIRES: int = int(os.environ.get("JWT_ACCESS_EXPIRES", "3600"))  # 1 hour
REFRESH_TOKEN_EXPIRES: int = int(os.environ.get("JWT_REFRESH_EXPIRES", "604800"))  # 7 days


@dataclass(frozen=True)
class TokenPayload:
    """Decoded JWT claims."""

    sub: str  # user_id
    role: str
    exp: int
    token_type: str  # "access" | "refresh"


def create_access_token(user_id: str, role: str) -> str:
    """Create a signed access JWT."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "exp": now + ACCESS_TOKEN_EXPIRES,
        "iat": now,
        "token_type": "access",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(user_id: str, role: str) -> str:
    """Create a signed refresh JWT."""
    now = int(time.time())
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "exp": now + REFRESH_TOKEN_EXPIRES,
        "iat": now,
        "token_type": "refresh",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """Decode and validate a JWT. Raises ``jwt.InvalidTokenError`` on failure."""
    data: dict[str, Any] = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    return TokenPayload(
        sub=data["sub"],
        role=data["role"],
        exp=data["exp"],
        token_type=data.get("token_type", "access"),
    )
