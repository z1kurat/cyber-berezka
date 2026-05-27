"""Auth: register / verify_email / authenticate. Pure business logic — no HTTP."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_opaque_token, hash_token_for_storage

MIN_PASSWORD_LEN = 12
# Brute-force lockout: after this many consecutive failed logins, the account
# is locked for LOCKOUT_DURATION. Counter resets on a successful login.
MAX_FAILED_LOGINS = 10
LOCKOUT_DURATION = timedelta(minutes=30)

# Pre-computed argon2id hash used to equalize timing when authenticate()
# is called for a non-existent email. Without this, verify_password is skipped
# for unknown emails, exposing an ~300ms timing oracle that distinguishes
# "email exists, wrong password" from "email does not exist".
_DUMMY_PASSWORD_HASH = hash_password("dummy-password-for-timing-equalization-2026")


class AuthError(Exception):
    pass


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        norm = email.strip().lower()
        result = await self.db.execute(select(User).where(User.email_normalized == norm))
        return result.scalar_one_or_none()

    async def register(self, email: str, password: str) -> tuple[User, str]:
        if len(password) < MIN_PASSWORD_LEN:
            raise AuthError("weak_password")
        norm = email.strip().lower()
        # Plaintext verify token is returned; only its hash is stored.
        verify_token = generate_opaque_token()
        user = User(
            email=email,
            email_normalized=norm,
            password_hash=hash_password(password),
            email_verify_token=hash_token_for_storage(verify_token),
        )
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise AuthError("email_taken")
        await self.db.refresh(user)
        return user, verify_token

    async def verify_email(self, verify_token: str) -> bool:
        token_hash = hash_token_for_storage(verify_token)
        result = await self.db.execute(
            select(User).where(User.email_verify_token == token_hash)
        )
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.email_verified_at = datetime.now(timezone.utc)
        user.email_verify_token = None
        await self.db.commit()
        return True

    async def authenticate(self, email: str, password: str) -> tuple[User | None, str | None]:
        user = await self.get_by_email(email)
        if user is None:
            verify_password(password, _DUMMY_PASSWORD_HASH)
            return None, "invalid_credentials"
        now = datetime.now(timezone.utc)
        if user.locked_until is not None:
            locked_until = user.locked_until
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=timezone.utc)
            if locked_until > now:
                verify_password(password, _DUMMY_PASSWORD_HASH)
                return None, "locked"
        if not verify_password(password, user.password_hash):
            user.failed_login_count = (user.failed_login_count or 0) + 1
            if user.failed_login_count >= MAX_FAILED_LOGINS:
                user.locked_until = now + LOCKOUT_DURATION
            await self.db.commit()
            return None, "invalid_credentials"
        if user.admin_rejected_at is not None:
            return None, "rejected"
        if not user.is_active:
            return None, "inactive"
        user.failed_login_count = 0
        user.locked_until = None
        user.last_login_at = now
        await self.db.commit()
        return user, None
