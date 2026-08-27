"""Verify webhook signatures over raw request bytes.

Verifying over a re-serialised dict passes every round-trip test and fails on
real traffic the moment key order or separator whitespace differs from the
sender's. The same reasoning applies to AuditEnvelope hash-chaining in Phase 1
— this helper is the pattern that code reuses.
"""

from __future__ import annotations

import hashlib
import hmac


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    """Return True when signature matches HMAC-SHA256 of raw_body with secret."""
    if not signature:
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    try:
        return hmac.compare_digest(expected, signature)
    except (TypeError, ValueError):
        return False
