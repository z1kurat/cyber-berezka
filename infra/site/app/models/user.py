"""User model — matches migration 0001 users table."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email_normalized: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    email_verify_token: Mapped[Optional[str]] = mapped_column(String(64))
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(64))
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    admin_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    admin_approved_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    admin_rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    admin_rejected_by: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("users.id"))
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    remnawave_user_uuid: Mapped[Optional[str]] = mapped_column(UUID(as_uuid=False), unique=True)
    remnawave_short_uuid: Mapped[Optional[str]] = mapped_column(String(64))

    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[Optional[str]] = mapped_column(INET)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_approved(self) -> bool:
        return self.admin_approved_at is not None

    @property
    def is_rejected(self) -> bool:
        return self.admin_rejected_at is not None
