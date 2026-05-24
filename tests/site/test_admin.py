"""Tests for admin approval/reject logic (service layer)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.user import User
from app.routers.admin import approve_user_service, reject_user_service


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest_asyncio.fixture
async def target_user(db):
    from datetime import datetime, timezone
    u = User(email="u@x", email_normalized="u@x", password_hash="x",
            email_verified_at=datetime.now(timezone.utc))
    db.add(u); await db.commit(); await db.refresh(u)
    return u


@pytest_asyncio.fixture
async def admin_user(db):
    from datetime import datetime, timezone
    u = User(email="a@x", email_normalized="a@x", password_hash="x", is_admin=True,
            email_verified_at=datetime.now(timezone.utc))
    db.add(u); await db.commit(); await db.refresh(u)
    return u


@pytest.mark.asyncio
async def test_approve_user_sets_approved_fields(db, target_user, admin_user):
    await approve_user_service(db, target_user, admin_user)
    await db.refresh(target_user)
    assert target_user.admin_approved_at is not None
    assert target_user.admin_approved_by == admin_user.id


@pytest.mark.asyncio
async def test_reject_user_sets_rejected_fields(db, target_user, admin_user):
    await reject_user_service(db, target_user, admin_user, reason="spam")
    await db.refresh(target_user)
    assert target_user.admin_rejected_at is not None
    assert target_user.rejection_reason == "spam"
