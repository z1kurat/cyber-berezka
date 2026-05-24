"""CSRF: HMAC-signed token bound to the session id (double-submit pattern)."""
from __future__ import annotations

import hashlib
import hmac

from app.config import settings

_CSRF_SECRET = settings.secret_key.encode("utf-8")


def generate_csrf(session_id: str) -> str:
    """Return a hex CSRF token bound to session_id, valid until session is revoked."""
    return hmac.new(_CSRF_SECRET, session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_csrf(session_id: str, submitted: str) -> bool:
    """Compare expected CSRF with submitted; constant-time."""
    expected = generate_csrf(session_id)
    return hmac.compare_digest(expected, submitted)
