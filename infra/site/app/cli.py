"""CLI utilities. Usage: python -m app.cli <command> [args].

Currently supports:
  promote-admin --email <email>   — set is_admin=True on the user with given email.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.db import async_session_factory
from app.models.user import User


async def promote_admin(email: str) -> int:
    norm = email.strip().lower()
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email_normalized == norm))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"ERROR: user with email {email} not found")
            return 1
        if user.is_admin:
            print(f"INFO: {email} is already an admin")
            return 0
        user.is_admin = True
        # Auto-approve admin so they can use the cabinet immediately.
        if user.admin_approved_at is None:
            from datetime import datetime, timezone
            user.admin_approved_at = datetime.now(timezone.utc)
            user.admin_approved_by = user.id
        await db.commit()
        print(f"OK: promoted {email} to admin and approved")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("promote-admin")
    p.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.cmd == "promote-admin":
        return asyncio.run(promote_admin(args.email))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
