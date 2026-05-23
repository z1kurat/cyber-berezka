"""Reality key rotation helpers for apply.py.

Closes design-spec task #28: regenerate the Reality x25519 keypair via the
Remnawave panel and persist it to the .env consumed by the node container.
"""
from __future__ import annotations

from pathlib import Path
from typing import Tuple


def rotate_reality_keys(client) -> Tuple[str, str]:
    """Call Remnawave x25519 generate endpoint, return (private, public)."""
    response = client.generate_x25519()
    return response["privateKey"], response["publicKey"]


def write_keys_to_env(env_path: Path, private_key: str, public_key: str) -> None:
    """Write REALITY_PRIVATE_KEY and REALITY_PUBLIC_KEY into env_path in-place.

    Replaces existing lines if present, appends otherwise. Creates the file
    if it does not exist. Preserves all other lines and ordering.
    """
    if not env_path.exists():
        env_path.write_text(
            f"REALITY_PRIVATE_KEY={private_key}\nREALITY_PUBLIC_KEY={public_key}\n"
        )
        return

    lines = env_path.read_text().splitlines()
    have_priv = False
    have_pub = False
    out: list[str] = []
    for line in lines:
        if line.startswith("REALITY_PRIVATE_KEY="):
            out.append(f"REALITY_PRIVATE_KEY={private_key}")
            have_priv = True
        elif line.startswith("REALITY_PUBLIC_KEY="):
            out.append(f"REALITY_PUBLIC_KEY={public_key}")
            have_pub = True
        else:
            out.append(line)

    if not have_priv:
        out.append(f"REALITY_PRIVATE_KEY={private_key}")
    if not have_pub:
        out.append(f"REALITY_PUBLIC_KEY={public_key}")

    env_path.write_text("\n".join(out) + "\n")
