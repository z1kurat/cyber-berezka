"""Common FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from redis.asyncio import Redis, from_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.user import User
from app.services.sessions import SessionService


_redis_client: Redis | None = None


async def get_redis() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def get_session_service(
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> SessionService:
    return SessionService(db, redis)


async def get_current_user(
    session_id: Annotated[str | None, Cookie(alias="__Host-session")] = None,
    svc: SessionService = Depends(get_session_service),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Returns User or None (anonymous). Routes can require auth on top of this."""
    if not session_id:
        return None
    sess = await svc.get(session_id)
    if sess is None:
        return None
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == sess.user_id))
    return result.scalar_one_or_none()


async def require_user(user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_303_SEE_OTHER, headers={"Location": "/auth/login"})
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user
