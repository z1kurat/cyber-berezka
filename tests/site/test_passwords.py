"""Tests for argon2id password helper."""
from __future__ import annotations

import pytest

from app.security.passwords import hash_password, verify_password


def test_hash_then_verify_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("right one")
    assert verify_password("wrong one", hashed) is False


def test_two_hashes_differ_due_to_salt():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b


def test_verify_with_malformed_hash_returns_false():
    assert verify_password("anything", "not-a-real-hash") is False
