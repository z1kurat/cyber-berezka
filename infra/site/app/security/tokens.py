"""Opaque token generation + storage hashing.

Pattern: generate a random URL-safe token, give it to the user, store only
its hash in the DB. On verify, hash the submitted token and look it up.
"""
from __future__ import annotations

import hashlib
import secrets


def generate_opaque_token(byte_len: int = 32) -> str:
    """Return a URL-safe base64 token of `byte_len` random bytes (no padding)."""
    return secrets.token_urlsafe(byte_len)


def hash_token_for_storage(token: str) -> str:
    """Return hex SHA-256 of the token — what we store in the DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
