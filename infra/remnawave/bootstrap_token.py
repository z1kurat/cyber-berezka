#!/usr/bin/env python3
"""bootstrap_token.py — save an API token issued through the panel UI.

Remnawave intentionally blocks /api/tokens for login-JWT requests (the API
returns "For API requests you must create own API-token in the admin
dashboard"). API tokens must be created through the panel UI by an admin.

Flow:
  1. In the panel UI: "Settings / Remnawave Settings → API Tokens → Create"
     and copy the generated token.
  2. Run this script and paste the token when prompted.
  3. Script validates it by calling GET /api/system/health and writes to .env.

Run again with --revalidate to re-check an existing token (no paste).
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

import httpx


def validate_token(base_url: str, token: str) -> dict:
    resp = httpx.get(
        f"{base_url.rstrip('/')}/api/system/health",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
        verify=True,
    )
    resp.raise_for_status()
    return resp.json()


def write_env(env_file: Path, base_url: str, token: str) -> None:
    if not env_file.exists():
        raise SystemExit(f".env not found at {env_file}")

    lines = env_file.read_text().splitlines()
    saw_url = False
    saw_token = False
    new_lines: list[str] = []
    for line in lines:
        if line.startswith("REMNAWAVE_API_URL="):
            new_lines.append(f"REMNAWAVE_API_URL={base_url}")
            saw_url = True
        elif line.startswith("REMNAWAVE_API_TOKEN="):
            new_lines.append(f"REMNAWAVE_API_TOKEN={token}")
            saw_token = True
        else:
            new_lines.append(line)
    if not saw_url:
        new_lines.append(f"REMNAWAVE_API_URL={base_url}")
    if not saw_token:
        new_lines.append(f"REMNAWAVE_API_TOKEN={token}")

    env_file.write_text("\n".join(new_lines) + "\n")
    env_file.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--base-url",
        default=os.environ.get("REMNAWAVE_API_URL", "https://admin.194-87-83-31.nip.io"),
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(__file__).resolve().parent.parent / ".env",
    )
    parser.add_argument(
        "--revalidate",
        action="store_true",
        help="Just check existing REMNAWAVE_API_TOKEN, don't prompt",
    )
    args = parser.parse_args()

    if args.revalidate:
        # Re-read .env so we use the value already on disk.
        if args.env_file.exists():
            for line in args.env_file.read_text().splitlines():
                if line.startswith("REMNAWAVE_API_TOKEN=") and "REMNAWAVE_API_TOKEN" not in os.environ:
                    os.environ["REMNAWAVE_API_TOKEN"] = line.split("=", 1)[1]
        token = os.environ.get("REMNAWAVE_API_TOKEN", "")
        if not token:
            print("No REMNAWAVE_API_TOKEN to revalidate.", file=sys.stderr)
            return 1
    else:
        print(
            f"\nBefore continuing:\n"
            f"  1. Open the panel UI: {args.base_url}\n"
            f"  2. Settings / Remnawave Settings → API Tokens → 'Add' (or 'Create')\n"
            f"  3. Name the token (e.g., 'cyber-berezka-apply').\n"
            f"  4. Copy the generated token string.\n"
        )
        token = getpass.getpass("Paste API token (hidden): ").strip()
        if not token:
            print("Empty token — aborting.", file=sys.stderr)
            return 1

    print(f"\nValidating against {args.base_url}/api/system/health ...", file=sys.stderr)
    try:
        info = validate_token(args.base_url, token)
    except httpx.HTTPStatusError as exc:
        print(f"Validation failed: {exc.response.status_code} {exc.response.text[:200]}", file=sys.stderr)
        return 2

    print(f"OK. Panel says: {info}")

    if args.revalidate:
        return 0

    write_env(args.env_file, args.base_url, token)
    print(f"\nWritten to {args.env_file} (chmod 600).", file=sys.stderr)
    print("Next: python3 apply.py status", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
