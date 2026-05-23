"""Tests for reality.py key rotation logic."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "infra" / "remnawave"))

from _lib.reality import rotate_reality_keys, write_keys_to_env  # noqa: E402


def test_rotate_calls_remnawave_x25519_endpoint():
    client = MagicMock()
    client.generate_x25519.return_value = {
        "privateKey": "PRIV_KEY_VALUE",
        "publicKey": "PUB_KEY_VALUE",
    }

    result = rotate_reality_keys(client)

    client.generate_x25519.assert_called_once()
    assert result == ("PRIV_KEY_VALUE", "PUB_KEY_VALUE")


def test_write_keys_to_env_updates_existing_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("FOO=bar\nREALITY_PRIVATE_KEY=OLD_PRIV\nREALITY_PUBLIC_KEY=OLD_PUB\nBAZ=qux\n")

    write_keys_to_env(env, "NEW_PRIV", "NEW_PUB")

    content = env.read_text().splitlines()
    assert "FOO=bar" in content
    assert "BAZ=qux" in content
    assert "REALITY_PRIVATE_KEY=NEW_PRIV" in content
    assert "REALITY_PUBLIC_KEY=NEW_PUB" in content
    assert "OLD_PRIV" not in env.read_text()


def test_write_keys_to_env_appends_when_missing(tmp_path):
    env = tmp_path / ".env"
    env.write_text("FOO=bar\n")

    write_keys_to_env(env, "P1", "P2")

    content = env.read_text()
    assert "REALITY_PRIVATE_KEY=P1" in content
    assert "REALITY_PUBLIC_KEY=P2" in content
    assert "FOO=bar" in content


def test_write_keys_to_env_creates_file_if_missing(tmp_path):
    env = tmp_path / ".env.new"
    write_keys_to_env(env, "P1", "P2")

    assert env.exists()
    text = env.read_text()
    assert "REALITY_PRIVATE_KEY=P1" in text
    assert "REALITY_PUBLIC_KEY=P2" in text
