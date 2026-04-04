"""TOTP utilities for multi-factor authentication."""

from __future__ import annotations

import pyotp


def generate_totp_secret() -> str:
    """Generate a new TOTP secret."""
    return pyotp.random_base32()


def get_provisioning_uri(secret: str, email: str, issuer: str = "Lintel") -> str:
    """Build an otpauth:// URI for QR code generation."""
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def verify_totp_code(secret: str, code: str) -> bool:
    """Verify a TOTP code against the secret. Allows ±1 window for clock drift."""
    totp = pyotp.TOTP(secret)
    return totp.verify(code, valid_window=1)
