"""Auth: register / verify_email / authenticate. Pure business logic — no HTTP."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.security.passwords import hash_password, verify_password
from app.security.tokens import generate_opaque_token, hash_token_for_storage

MIN_PASSWORD_LEN = 12


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
        from datetime import datetime, timezone
        user.email_verified_at = datetime.now(timezone.utc)
        user.email_verify_token = None
        await self.db.commit()
        return True

    async def authenticate(self, email: str, password: str) -> tuple[User | None, str | None]:
        user = await self.get_by_email(email)
        if user is None:
            return None, "invalid_credentials"
        if not verify_password(password, user.password_hash):
            return None, "invalid_credentials"
        if user.admin_rejected_at is not None:
            return None, "rejected"
        if not user.is_active:
            return None, "inactive"
        return user, None
