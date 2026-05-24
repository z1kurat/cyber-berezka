"""Tests for the session service (Postgres-equivalent SQLite + fake Redis)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.services.sessions import SessionService


class FakeRedis:
    def __init__(self):
        self.store = {}
    async def get(self, k):
        return self.store.get(k)
    async def setex(self, k, ttl, v):
        self.store[k] = v
    async def delete(self, k):
        self.store.pop(k, None)


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def user(db_session: AsyncSession):
    u = User(
        email="a@b.com", email_normalized="a@b.com", password_hash="x",
    )
    db_session.add(u)
    await db_session.commit()
    await db_session.refresh(u)
    return u


@pytest.mark.asyncio
async def test_create_then_get_session(db_session, user):
    svc = SessionService(db_session, FakeRedis())
    sid = await svc.create(user_id=user.id, ip="1.2.3.4", ua="UA")
    assert len(sid) == 43
    sess = await svc.get(sid)
    assert sess is not None
    assert sess.user_id == user.id


@pytest.mark.asyncio
async def test_revoke_session(db_session, user):
    svc = SessionService(db_session, FakeRedis())
    sid = await svc.create(user_id=user.id)
    await svc.revoke(sid)
    assert await svc.get(sid) is None


@pytest.mark.asyncio
async def test_expired_session_not_returned(db_session, user):
    svc = SessionService(db_session, FakeRedis())
    sid = await svc.create(user_id=user.id, ttl_hours=-1)  # already expired
    assert await svc.get(sid) is None
