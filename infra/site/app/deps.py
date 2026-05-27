"""Common FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from redis.asyncio import Redis, from_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.user import User
from app.security.csrf import verify_csrf
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
    session_id: Annotated[str | None, Cookie(alias="session")] = None,
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


async def require_user(
    request: Request,
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None:
        accept = request.headers.get("accept", "")
        if "text/html" in accept.lower():
            raise HTTPException(
                status_code=status.HTTP_303_SEE_OTHER,
                headers={"Location": "/auth/login"},
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not_authenticated",
        )
    return user


async def require_admin(user: User = Depends(require_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
    return user


async def verify_csrf_token(
    request: Request,
    session_id: Annotated[str | None, Cookie(alias="session")] = None,
) -> None:
    """Verify CSRF token submitted with a state-changing request.

    Uses the double-submit pattern: token is HMAC(secret, session_id), so the
    server can recompute it from the cookie alone. Submitted token comes from
    form field `csrf_token` or header `X-CSRF-Token`.

    Routes used pre-session (login, register, email verify) MUST NOT use this
    dependency — there is no session_id to bind against.
    """
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="csrf_no_session",
        )
    submitted = request.headers.get("x-csrf-token", "")
    if not submitted:
        try:
            form = await request.form()
            submitted = str(form.get("csrf_token", ""))
        except Exception:
            submitted = ""
    if not submitted or not verify_csrf(session_id, submitted):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="csrf_invalid",
        )
