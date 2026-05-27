#!/usr/bin/env python3
"""apply.py — Declarative Remnawave provisioning.

Stage 2 (this commit): read-only `status` command that calls the Remnawave
REST API and prints current state. Bootstrap requires REMNAWAVE_API_URL
and REMNAWAVE_API_TOKEN in the environment (typically loaded from .env).

Design: docs/superpowers/specs/2026-05-17-apply-py-design.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add _lib/ to sys.path so we can import without installing the package.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _lib.client import RemnawaveClient, RemnawaveError  # noqa: E402


def _load_env_file(path: Path) -> None:
    """Minimal .env loader: KEY=VALUE per line. Skips comments and blanks.

    Does not interpolate, does not strip quotes — values are taken verbatim
    after the first '='. Good enough for our .env where secrets are hex/base64.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        # Only set if not already in environment so explicit env wins.
        import os
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value


def _print_section(title: str, rows: list[tuple[str, str]]) -> None:
    print(f"\n=== {title} ({len(rows)}) ===")
    if not rows:
        print("  (none)")
        return
    width = max((len(k) for k, _ in rows), default=0)
    for key, val in rows:
        print(f"  {key:<{width}}  {val}")


def cmd_status(client: RemnawaveClient) -> int:
    try:
        health = client.health()
        print(f"Panel health: {health}")
    except RemnawaveError as exc:
        print(f"Panel /health failed: {exc}", file=sys.stderr)
        return 2

    try:
        profiles = client.list_profiles()
        squads = client.list_squads()
        nodes = client.list_nodes()
        hosts = client.list_hosts()
        users_resp = client.list_users(size=200)
    except RemnawaveError as exc:
        print(f"API call failed: {exc}", file=sys.stderr)
        return 2

    # Profiles
    rows = [(p.get("name", "?"), p.get("uuid", "?")) for p in (profiles or [])]
    _print_section("Config Profiles", rows)

    # Squads
    rows = []
    for s in squads or []:
        info = s.get("info") or {}
        rows.append((
            s.get("name", "?"),
            f"members={info.get('membersCount', '?')}, inbounds={info.get('inboundsCount', '?')}, uuid={s.get('uuid','?')}",
        ))
    _print_section("Internal Squads", rows)

    # Nodes
    rows = []
    for n in nodes or []:
        connected = n.get("isConnected")
        flag = "✓" if connected else ("…" if n.get("isConnecting") else "✗")
        rows.append((
            f"{flag} {n.get('name', '?')}",
            f"{n.get('address', '?')}:{n.get('port', '?')} country={n.get('countryCode','?')}",
        ))
    _print_section("Nodes", rows)

    # Hosts
    rows = []
    for h in hosts or []:
        rows.append((
            h.get("remark", "?"),
            f"{h.get('address', '?')}:{h.get('port', '?')} sni={h.get('sni','?')}",
        ))
    _print_section("Hosts", rows)

    # Users
    total = 0
    rows = []
    if isinstance(users_resp, dict):
        total = users_resp.get("total", 0)
        for u in users_resp.get("users", []):
            rows.append((
                u.get("username", "?"),
                f"status={u.get('status','?')} short={u.get('shortUuid','?')}",
            ))
    _print_section(f"Users (total={total})", rows)

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Declarative Remnawave provisioning (read-only stage)",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=HERE.parent / ".env",
        help="Path to .env (default: infra/.env, relative to apply.py)",
    )
    subs = parser.add_subparsers(dest="cmd", required=True)
    subs.add_parser("status", help="show current Remnawave state")
    p_import = subs.add_parser(
        "import",
        help="dump current Remnawave state to configs/*.yaml + state.json (Terraform-style)",
    )
    p_import.add_argument(
        "--out-dir",
        type=Path,
        default=HERE / "configs",
        help="Directory for generated YAML (default: infra/remnawave/configs/)",
    )
    p_import.add_argument(
        "--state-file",
        type=Path,
        default=HERE / "state.json",
        help="Path for state.json (default: infra/remnawave/state.json)",
    )
    p_rotate = subs.add_parser(
        "rotate-reality-key",
        help="generate new Reality keypair via Remnawave x25519 endpoint, write to .env",
    )
    p_rotate.add_argument(
        "--env-file-target",
        type=Path,
        default=HERE.parent / ".env",
        help="Path to .env where new keys are written (default: infra/.env)",
    )
    # Stages to follow: plan, apply, validate, destroy.
    args = parser.parse_args(argv)

    _load_env_file(args.env_file)

    try:
        with RemnawaveClient() as client:
            if args.cmd == "status":
                return cmd_status(client)
            if args.cmd == "import":
                from _lib.importer import cmd_import
                return cmd_import(client, args.out_dir, args.state_file)
            if args.cmd == "rotate-reality-key":
                from _lib.reality import rotate_reality_keys, write_keys_to_env
                priv, pub = rotate_reality_keys(client)
                write_keys_to_env(args.env_file_target, priv, pub)
                print(f"Reality keys rotated. Written to {args.env_file_target}")
                print(f"Public key (use for hosts.yaml / clients): {pub}")
                return 0
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        print(
            "Set REMNAWAVE_API_URL (e.g., https://admin.example.com) and "
            "REMNAWAVE_API_TOKEN in the .env file.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
