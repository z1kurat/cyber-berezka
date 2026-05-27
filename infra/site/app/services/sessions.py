"""Session create / get / revoke; Postgres canonical + optional Redis cache.

The plaintext session id lives only in the cookie sent to the user.
The DB stores SHA-256(plaintext), so a read-only DB compromise (SQLi,
backup leak, replica access) cannot directly produce working cookies.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.session import Session
from app.security.tokens import generate_opaque_token, hash_token_for_storage


class SessionService:
    def __init__(self, db: AsyncSession, redis):
        self.db = db
        self.redis = redis

    async def create(
        self,
        user_id: int,
        ip: str | None = None,
        ua: str | None = None,
        ttl_hours: int | None = None,
    ) -> str:
        sid = generate_opaque_token()
        sid_hash = hash_token_for_storage(sid)
        ttl = ttl_hours if ttl_hours is not None else settings.session_lifetime_hours
        expires = datetime.now(timezone.utc) + timedelta(hours=ttl)
        sess = Session(
            id=sid_hash, user_id=user_id, expires_at=expires,
            ip_address=ip, user_agent=ua,
        )
        self.db.add(sess)
        await self.db.commit()
        if ttl > 0:
            await self.redis.setex(f"sess:{sid_hash}", ttl * 3600, str(user_id))
        return sid

    async def get(self, sid: str) -> Session | None:
        """Return the Session if valid (not expired, not revoked), else None."""
        sid_hash = hash_token_for_storage(sid)
        result = await self.db.execute(select(Session).where(Session.id == sid_hash))
        sess = result.scalar_one_or_none()
        if sess is None or not sess.is_valid:
            return None
        return sess

    async def revoke(self, sid: str) -> None:
        sid_hash = hash_token_for_storage(sid)
        result = await self.db.execute(select(Session).where(Session.id == sid_hash))
        sess = result.scalar_one_or_none()
        if sess is not None:
            sess.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
        await self.redis.delete(f"sess:{sid_hash}")
