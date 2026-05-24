"""Session create / get / revoke; Postgres canonical + optional Redis cache."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.session import Session
from app.security.tokens import generate_opaque_token


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
        ttl = ttl_hours if ttl_hours is not None else settings.session_lifetime_hours
        expires = datetime.now(timezone.utc) + timedelta(hours=ttl)
        sess = Session(
            id=sid, user_id=user_id, expires_at=expires,
            ip_address=ip, user_agent=ua,
        )
        self.db.add(sess)
        await self.db.commit()
        if ttl > 0:
            await self.redis.setex(f"sess:{sid}", ttl * 3600, str(user_id))
        return sid

    async def get(self, sid: str) -> Session | None:
        """Return the Session if valid (not expired, not revoked), else None."""
        result = await self.db.execute(select(Session).where(Session.id == sid))
        sess = result.scalar_one_or_none()
        if sess is None or not sess.is_valid:
            return None
        return sess

    async def revoke(self, sid: str) -> None:
        result = await self.db.execute(select(Session).where(Session.id == sid))
        sess = result.scalar_one_or_none()
        if sess is not None:
            sess.revoked_at = datetime.now(timezone.utc)
            await self.db.commit()
        await self.redis.delete(f"sess:{sid}")
