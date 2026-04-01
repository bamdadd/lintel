"""HMAC-SHA256 signature verification for GitHub webhooks."""

from __future__ import annotations

import hashlib
import hmac


def verify_github_signature(secret: str, body: bytes, signature_header: str) -> bool:
    """Verify a GitHub webhook payload against the X-Hub-Signature-256 header.

    Args:
        secret: The webhook secret configured for the repository.
        body: The raw request body bytes.
        signature_header: The value of the X-Hub-Signature-256 header
            (e.g. ``sha256=abc123...``).

    Returns:
        ``True`` if the signature is valid, ``False`` otherwise.

    Raises:
        ValueError: If the signature header is malformed (missing ``sha256=`` prefix).
    """
    if not signature_header.startswith("sha256="):
        msg = (
            f"Malformed signature header: expected 'sha256=<hex>' prefix, "
            f"got '{signature_header[:20]}...'"
        )
        raise ValueError(msg)

    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    received = signature_header[len("sha256=") :]
    return hmac.compare_digest(expected, received)
