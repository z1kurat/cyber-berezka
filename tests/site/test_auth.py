"""Tests for AuthService (register, verify_email, authenticate)."""
from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.services.auth import AuthError, AuthService


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_register_creates_user_with_verify_token(db):
    svc = AuthService(db)
    user, verify_token = await svc.register(email="a@b.com", password="some_pw_12_chars")
    assert user.email == "a@b.com"
    assert user.email_verified_at is None
    assert user.email_verify_token is not None
    assert len(verify_token) == 43


@pytest.mark.asyncio
async def test_register_duplicate_email_raises(db):
    svc = AuthService(db)
    await svc.register(email="a@b.com", password="pwpwpwpwpwpw")
    with pytest.raises(AuthError, match="email_taken"):
        await svc.register(email="a@b.com", password="other12chars")


@pytest.mark.asyncio
async def test_register_rejects_short_password(db):
    svc = AuthService(db)
    with pytest.raises(AuthError, match="weak_password"):
        await svc.register(email="a@b.com", password="short")


@pytest.mark.asyncio
async def test_verify_email_marks_user_verified(db):
    svc = AuthService(db)
    user, token = await svc.register(email="a@b.com", password="pwpwpwpwpwpw")
    ok = await svc.verify_email(token)
    assert ok is True
    refreshed = await svc.get_by_email("a@b.com")
    assert refreshed.email_verified_at is not None
    assert refreshed.email_verify_token is None  # token cleared after use


@pytest.mark.asyncio
async def test_verify_email_with_invalid_token_returns_false(db):
    svc = AuthService(db)
    assert await svc.verify_email("not-a-real-token") is False


@pytest.mark.asyncio
async def test_authenticate_correct_password(db):
    svc = AuthService(db)
    await svc.register(email="a@b.com", password="pwpwpwpwpwpw")
    user, err = await svc.authenticate("a@b.com", "pwpwpwpwpwpw")
    assert err is None
    assert user is not None
    assert user.email == "a@b.com"


@pytest.mark.asyncio
async def test_authenticate_wrong_password_returns_error(db):
    svc = AuthService(db)
    await svc.register(email="a@b.com", password="pwpwpwpwpwpw")
    user, err = await svc.authenticate("a@b.com", "wrongpassword")
    assert user is None
    assert err == "invalid_credentials"


@pytest.mark.asyncio
async def test_authenticate_rejected_user_blocks_login(db):
    from datetime import datetime, timezone
    svc = AuthService(db)
    user, _ = await svc.register(email="a@b.com", password="pwpwpwpwpwpw")
    user.admin_rejected_at = datetime.now(timezone.utc)
    user.rejection_reason = "test reason"
    await db.commit()
    u, err = await svc.authenticate("a@b.com", "pwpwpwpwpwpw")
    assert u is None
    assert err == "rejected"
