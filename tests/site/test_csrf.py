"""CSRF token tests."""
from __future__ import annotations

from app.security.csrf import generate_csrf, verify_csrf
from app.security.tokens import generate_opaque_token, hash_token_for_storage


def test_csrf_generate_and_verify():
    token = generate_csrf("session-id-123")
    assert verify_csrf("session-id-123", token) is True


def test_csrf_mismatch_session_id():
    token = generate_csrf("session-id-A")
    assert verify_csrf("session-id-B", token) is False


def test_csrf_tampered_token_fails():
    token = generate_csrf("sid")
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert verify_csrf("sid", tampered) is False


def test_opaque_token_length_and_charset():
    t = generate_opaque_token()
    assert len(t) == 43  # urlsafe-base64 of 32 bytes, no padding
    assert all(c.isalnum() or c in "-_" for c in t)


def test_hash_token_is_sha256_hex():
    h = hash_token_for_storage("some-token")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
