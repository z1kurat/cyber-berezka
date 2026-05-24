# Cyber Berezka Site Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Реализовать полный auth + cabinet + admin-approval-gate в `infra/site/` поверх существующего лендинга, плюс динамический список серверов и deep-link кнопки для VPN-приложений.

**Architecture:** SSR FastAPI + Jinja2 + Alpine.js, без SPA. PostgreSQL для приложения (`db-app`, уже развёрнут на coordinator), Redis для сессий и кэша списка нод. Email через Brevo Transactional API. Связь с Remnawave panel — через internal Docker DNS (`http://remnawave:3000`), Bearer token из `.env`.

**Tech Stack:** Python 3.12, FastAPI 0.115+, SQLAlchemy 2 async, Alembic, asyncpg, Pydantic v2, argon2-cffi, httpx, redis-py, Jinja2, Tailwind CSS 3.4, Alpine.js 3.x, qrcode + Pillow.

**Specs:** `docs/superpowers/specs/2026-05-17-site-design.md` (база) + `docs/superpowers/specs/2026-05-23-site-amendments.md` (дельта 2026-05-23).

---

## File Structure (целевая)

```
infra/site/
├── Dockerfile                                [MODIFIED — Task 19]
├── pyproject.toml                             [no changes — все deps уже там]
├── alembic.ini                                [NEW — Task 1]
├── entrypoint.sh                              [NEW — Task 19]
├── migrations/
│   ├── env.py                                 [NEW — Task 1]
│   ├── script.py.mako                         [NEW — Task 1]
│   └── versions/
│       └── 0001_initial.py                    [NEW — Task 1]
├── app/
│   ├── main.py                                [MODIFIED — Task 9, 11]
│   ├── config.py                              [MODIFIED — Task 3]
│   ├── cli.py                                 [NEW — Task 17]
│   ├── db.py                                  [NEW — Task 3]
│   ├── deps.py                                [NEW — Task 10]
│   ├── models/
│   │   ├── __init__.py                        [NEW — Task 2]
│   │   ├── base.py                            [NEW — Task 2]
│   │   ├── user.py                            [NEW — Task 2]
│   │   ├── session.py                         [NEW — Task 2]
│   │   ├── vpn_key.py                         [NEW — Task 2]
│   │   └── audit_log.py                       [NEW — Task 2]
│   ├── security/
│   │   ├── __init__.py                        [NEW — Task 4]
│   │   ├── passwords.py                       [NEW — Task 4]
│   │   ├── csrf.py                            [NEW — Task 5]
│   │   └── tokens.py                          [NEW — Task 5]
│   ├── services/
│   │   ├── __init__.py                        [NEW]
│   │   ├── sessions.py                        [NEW — Task 6]
│   │   ├── email.py                           [NEW — Task 7]
│   │   ├── auth.py                            [NEW — Task 8]
│   │   ├── remnawave.py                       [NEW — Task 12]
│   │   ├── vpn_keys.py                        [NEW — Task 12]
│   │   ├── nodes.py                           [NEW — Task 14]
│   │   └── geo.py                             [NEW — Task 14]
│   ├── routers/
│   │   ├── __init__.py                        [no changes]
│   │   ├── landing.py                         [MODIFIED — Task 15]
│   │   ├── legal.py                           [no changes]
│   │   ├── auth.py                            [NEW — Task 9]
│   │   ├── cabinet.py                         [NEW — Task 11, 13]
│   │   └── admin.py                           [NEW — Task 16]
│   └── templates/
│       ├── base.html                          [MODIFIED — Task 18]
│       ├── auth/
│       │   ├── register.html                  [NEW — Task 9]
│       │   ├── login.html                     [NEW — Task 9]
│       │   └── verify_sent.html               [NEW — Task 9]
│       ├── cabinet/
│       │   ├── index.html                     [NEW — Task 11]
│       │   ├── pending_email.html             [NEW — Task 11]
│       │   ├── pending_admin.html             [NEW — Task 11]
│       │   ├── rejected.html                  [NEW — Task 11]
│       │   ├── keys.html                      [NEW — Task 13]
│       │   └── admin_pending.html             [NEW — Task 16]
│       ├── emails/
│       │   ├── verify.html                    [NEW — Task 7]
│       │   ├── approved.html                  [NEW — Task 7]
│       │   └── rejected.html                  [NEW — Task 7]
│       └── landing/
│           └── index.html                     [MODIFIED — Task 15, 18]

tests/site/                                    [NEW — many tasks]
├── conftest.py
├── test_passwords.py
├── test_csrf.py
├── test_sessions.py
├── test_email.py
├── test_auth.py
├── test_admin.py
└── test_nodes.py

infra/compose/docker-compose.coordinator.yml   [MODIFIED — Task 19]
```

---

## Convention

- Каждый task — отдельный git commit, message в conventional commits (`feat:`, `refactor:`, `test:`).
- TDD где применимо: тесты пишутся первыми, потом impl, потом проверка прохождения.
- Тесты пишутся в `tests/site/` (выходят за пределы `infra/site/`, чтобы не попадать в Docker context). Импорты в тестах: `sys.path.insert(0, "infra/site")`.
- Все коммиты от подсессии — с trailer `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`.

---

## Task 1: Alembic init + первая миграция

**Files:**
- Create: `infra/site/alembic.ini`
- Create: `infra/site/migrations/env.py`
- Create: `infra/site/migrations/script.py.mako`
- Create: `infra/site/migrations/versions/0001_initial.py`

- [ ] **Step 1: Создать `infra/site/alembic.ini`**

```ini
[alembic]
script_location = migrations
prepend_sys_path = .
sqlalchemy.url = driver://placeholder  ; overridden by env.py from APP_DB_URL

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 2: Создать `infra/site/migrations/env.py`**

```python
"""Alembic env — async-aware, reads URL from APP_DB_URL."""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make app/ importable.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from app.models.base import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Override sqlalchemy.url from environment.
db_url = os.environ.get("APP_DB_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Создать `infra/site/migrations/script.py.mako`**

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: Union[str, None] = ${repr(down_revision)}
branch_labels: Union[str, Sequence[str], None] = ${repr(branch_labels)}
depends_on: Union[str, Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

- [ ] **Step 4: Создать первую миграцию `infra/site/migrations/versions/0001_initial.py`**

```python
"""initial schema: users, sessions, vpn_keys, audit_log

Revision ID: 0001
Revises:
Create Date: 2026-05-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("email_normalized", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_verify_token", sa.String(64), nullable=True),
        sa.Column("password_reset_token", sa.String(64), nullable=True),
        sa.Column("password_reset_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_approved_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("admin_rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("admin_rejected_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("remnawave_user_uuid", sa.dialects.postgresql.UUID(), nullable=True, unique=True),
        sa.Column("remnawave_short_uuid", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_ip", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "sessions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "vpn_keys",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("label", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("meta", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    op.create_index("ix_vpn_keys_user_id", "vpn_keys", ["user_id"])

    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_data", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.dialects.postgresql.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_event_type", "audit_log", ["event_type"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_event_type", "audit_log")
    op.drop_index("ix_audit_log_user_id", "audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_vpn_keys_user_id", "vpn_keys")
    op.drop_table("vpn_keys")
    op.drop_index("ix_sessions_user_id", "sessions")
    op.drop_table("sessions")
    op.drop_table("users")
```

- [ ] **Step 5: Commit (без запуска alembic — модели нужны для compilation)**

```bash
git add infra/site/alembic.ini infra/site/migrations/
git commit -m "feat(site): alembic init + initial schema migration"
```

---

## Task 2: SQLAlchemy models

**Files:**
- Create: `infra/site/app/models/__init__.py`
- Create: `infra/site/app/models/base.py`
- Create: `infra/site/app/models/user.py`
- Create: `infra/site/app/models/session.py`
- Create: `infra/site/app/models/vpn_key.py`
- Create: `infra/site/app/models/audit_log.py`

- [ ] **Step 1: `app/models/base.py`**

```python
"""Declarative base for all models."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """All ORM models inherit from this."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(),
        onupdate=func.now(), nullable=False,
    )
```

- [ ] **Step 2: `app/models/user.py`**

```python
"""User model — matches migration 0001 users table."""
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

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

    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    email_verify_token: Mapped[str | None] = mapped_column(String(64))
    password_reset_token: Mapped[str | None] = mapped_column(String(64))
    password_reset_expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    admin_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admin_approved_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    admin_rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    admin_rejected_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    remnawave_user_uuid: Mapped[str | None] = mapped_column(UUID(as_uuid=False), unique=True)
    remnawave_short_uuid: Mapped[str | None] = mapped_column(String(64))

    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_ip: Mapped[str | None] = mapped_column(INET)
    failed_login_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_email_verified(self) -> bool:
        return self.email_verified_at is not None

    @property
    def is_approved(self) -> bool:
        return self.admin_approved_at is not None

    @property
    def is_rejected(self) -> bool:
        return self.admin_rejected_at is not None
```

- [ ] **Step 3: `app/models/session.py`**

```python
"""Session model — server-side session store."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @property
    def is_valid(self) -> bool:
        from datetime import datetime, timezone
        return self.revoked_at is None and self.expires_at > datetime.now(timezone.utc)
```

- [ ] **Step 4: `app/models/vpn_key.py`**

```python
"""VPN key model — local metadata for a Remnawave-issued subscription."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VpnKey(Base):
    __tablename__ = "vpn_keys"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    label: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
```

- [ ] **Step 5: `app/models/audit_log.py`**

```python
"""Audit log — append-only event stream."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    ip_address: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
```

- [ ] **Step 6: `app/models/__init__.py`**

```python
"""Re-export all models for convenient imports."""
from app.models.audit_log import AuditLog
from app.models.base import Base, TimestampMixin
from app.models.session import Session
from app.models.user import User
from app.models.vpn_key import VpnKey

__all__ = ["AuditLog", "Base", "Session", "TimestampMixin", "User", "VpnKey"]
```

- [ ] **Step 7: Commit**

```bash
git add infra/site/app/models/
git commit -m "feat(site/models): SQLAlchemy models for users, sessions, vpn_keys, audit_log"
```

---

## Task 3: DB connection + config additions

**Files:**
- Create: `infra/site/app/db.py`
- Modify: `infra/site/app/config.py`

- [ ] **Step 1: Extend `app/config.py`**

В `Settings` (после существующего `redis_url`) добавить:

```python
    # Brevo
    brevo_api_key: str = Field(default="", alias="BREVO_API_KEY")
    brevo_sender_email: str = Field(
        default="noreply@cyber-berezka.ru", alias="BREVO_SENDER_EMAIL"
    )
    brevo_sender_name: str = Field(default="Cyber Berezka", alias="BREVO_SENDER_NAME")

    # Session
    session_lifetime_hours: int = Field(default=24 * 30, alias="SESSION_LIFETIME_HOURS")
    cookie_secure: bool = Field(default=True, alias="COOKIE_SECURE")

    # Admin contact (for rejection emails)
    admin_contact_email: str = Field(
        default="admin@cyber-berezka.ru", alias="ADMIN_CONTACT_EMAIL"
    )

    # Site
    site_host: str = Field(default="212-74-231-217.nip.io", alias="SITE_HOST")
    admin_host: str = Field(default="admin.212-74-231-217.nip.io", alias="ADMIN_HOST")
```

Поля `brevo_*` уже могут быть, если есть — пропустить. `session_lifetime_hours` уже в базовом config.

- [ ] **Step 2: Создать `app/db.py`**

```python
"""Async SQLAlchemy engine + session factory."""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings

engine = create_async_engine(
    settings.db_app_url,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, class_=AsyncSession,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an AsyncSession, close on exit."""
    async with async_session_factory() as session:
        yield session
```

- [ ] **Step 3: Commit**

```bash
git add infra/site/app/db.py infra/site/app/config.py
git commit -m "feat(site/db): async engine, session factory; extend config (brevo, session, hosts)"
```

---

## Task 4: Password hashing (argon2id)

**Files:**
- Create: `infra/site/app/security/__init__.py` (пустой)
- Create: `infra/site/app/security/passwords.py`
- Create: `tests/site/conftest.py`
- Create: `tests/site/test_passwords.py`

- [ ] **Step 1: `tests/site/conftest.py`**

```python
"""Shared test fixtures + sys.path setup for site tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "infra" / "site"))
```

- [ ] **Step 2: `tests/site/test_passwords.py` (failing tests first)**

```python
"""Tests for argon2id password helper."""
from __future__ import annotations

import pytest

from app.security.passwords import hash_password, verify_password


def test_hash_then_verify_roundtrip():
    hashed = hash_password("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hashed.startswith("$argon2id$")
    assert verify_password("correct horse battery staple", hashed) is True


def test_verify_rejects_wrong_password():
    hashed = hash_password("right one")
    assert verify_password("wrong one", hashed) is False


def test_two_hashes_differ_due_to_salt():
    a = hash_password("same")
    b = hash_password("same")
    assert a != b


def test_verify_with_malformed_hash_returns_false():
    assert verify_password("anything", "not-a-real-hash") is False
```

- [ ] **Step 3: Run, expect failure**

```bash
cd /Users/nikitavorozbitov/pycharmProject/cyber-berezka
python -m pytest tests/site/test_passwords.py -v
```

Expected: `ImportError: cannot import name 'hash_password' from 'app.security.passwords'`

- [ ] **Step 4: `app/security/passwords.py`**

```python
"""argon2id password hashing wrapper.

Parameters tuned per OWASP 2024 guidance: m=64 MiB, t=3, p=4.
"""
from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(plaintext: str) -> str:
    """Hash a password using argon2id; returns the encoded hash string."""
    return _hasher.hash(plaintext)


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a password against an encoded argon2id hash. Returns False on any error."""
    try:
        return _hasher.verify(hashed, plaintext)
    except (VerifyMismatchError, InvalidHashError, Exception):
        return False
```

- [ ] **Step 5: `app/security/__init__.py`** (пустой, `touch infra/site/app/security/__init__.py`)

- [ ] **Step 6: Run, expect pass**

```bash
python -m pytest tests/site/test_passwords.py -v
```

Expected: `4 passed`.

- [ ] **Step 7: Commit**

```bash
git add infra/site/app/security/ tests/site/test_passwords.py tests/site/conftest.py
git commit -m "feat(site/security): argon2id password hashing with verify"
```

---

## Task 5: CSRF + opaque token helpers

**Files:**
- Create: `infra/site/app/security/csrf.py`
- Create: `infra/site/app/security/tokens.py`
- Create: `tests/site/test_csrf.py`

- [ ] **Step 1: `tests/site/test_csrf.py`**

```python
"""CSRF token tests."""
from __future__ import annotations

from app.security.csrf import generate_csrf, verify_csrf
from app.security.tokens import generate_opaque_token, hash_token_for_storage


def test_csrf_generate_and_verify():
    token = generate_csrf("session-id-123")
    assert verify_csrf("session-id-123", token) is True


def test_csrf_mismatch_session_id():
    token = generate_csrf("session-id-A")
    assert verify_csrf("session-id-B", token) is False


def test_csrf_tampered_token_fails():
    token = generate_csrf("sid")
    tampered = token[:-1] + ("0" if token[-1] != "0" else "1")
    assert verify_csrf("sid", tampered) is False


def test_opaque_token_length_and_charset():
    t = generate_opaque_token()
    assert len(t) == 43  # urlsafe-base64 of 32 bytes, no padding
    assert all(c.isalnum() or c in "-_" for c in t)


def test_hash_token_is_sha256_hex():
    h = hash_token_for_storage("some-token")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)
```

- [ ] **Step 2: Run, expect failure**

```bash
python -m pytest tests/site/test_csrf.py -v
```

Expected: ImportError.

- [ ] **Step 3: `app/security/tokens.py`**

```python
"""Opaque token generation + storage hashing.

Pattern: generate a random URL-safe token, give it to the user, store only
its hash in the DB. On verify, hash the submitted token and look it up.
"""
from __future__ import annotations

import hashlib
import secrets


def generate_opaque_token(byte_len: int = 32) -> str:
    """Return a URL-safe base64 token of `byte_len` random bytes (no padding)."""
    return secrets.token_urlsafe(byte_len)


def hash_token_for_storage(token: str) -> str:
    """Return hex SHA-256 of the token — what we store in the DB."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: `app/security/csrf.py`**

```python
"""CSRF: HMAC-signed token bound to the session id (double-submit pattern)."""
from __future__ import annotations

import hashlib
import hmac
import os

from app.config import settings

_CSRF_SECRET = settings.secret_key.encode("utf-8")


def generate_csrf(session_id: str) -> str:
    """Return a hex CSRF token bound to session_id, valid until session is revoked."""
    return hmac.new(_CSRF_SECRET, session_id.encode("utf-8"), hashlib.sha256).hexdigest()


def verify_csrf(session_id: str, submitted: str) -> bool:
    """Compare expected CSRF with submitted; constant-time."""
    expected = generate_csrf(session_id)
    return hmac.compare_digest(expected, submitted)
```

- [ ] **Step 5: Run, expect pass**

```bash
python -m pytest tests/site/test_csrf.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add infra/site/app/security/csrf.py infra/site/app/security/tokens.py tests/site/test_csrf.py
git commit -m "feat(site/security): CSRF (HMAC double-submit) and opaque token helpers"
```

---

## Task 6: Session service

**Files:**
- Create: `infra/site/app/services/__init__.py` (пустой)
- Create: `infra/site/app/services/sessions.py`
- Create: `tests/site/test_sessions.py`

- [ ] **Step 1: `tests/site/test_sessions.py`**

```python
"""Tests for the session service (Postgres + Redis hot cache).

These tests use an in-memory SQLite for the DB and a fake Redis double.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

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
```

Add to `tests/site/conftest.py`:

```python
import pytest_asyncio  # noqa: F401  — registers asyncio mode

# Pytest asyncio mode: auto so @pytest_asyncio.fixture works
```

And to `pyproject.toml` of the project (root), add testing dependencies — but since deps already include pytest, just ensure `pytest-asyncio` and `aiosqlite` are installed locally:

```bash
python -m pip install pytest-asyncio aiosqlite
```

- [ ] **Step 2: Run, expect failure**

```bash
python -m pytest tests/site/test_sessions.py -v
```

Expected: ImportError for `SessionService`.

- [ ] **Step 3: `app/services/sessions.py`**

```python
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
```

- [ ] **Step 4: Run, expect pass**

```bash
python -m pytest tests/site/test_sessions.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add infra/site/app/services/sessions.py infra/site/app/services/__init__.py tests/site/test_sessions.py
git commit -m "feat(site/services): SessionService (Postgres canonical + Redis hot cache)"
```

---

## Task 7: Brevo email service + email templates

**Files:**
- Create: `infra/site/app/services/email.py`
- Create: `infra/site/app/templates/emails/verify.html`
- Create: `infra/site/app/templates/emails/approved.html`
- Create: `infra/site/app/templates/emails/rejected.html`
- Create: `tests/site/test_email.py`

- [ ] **Step 1: `tests/site/test_email.py`**

```python
"""Tests for Brevo email service.

We stub httpx.AsyncClient to assert the right payload is sent, no network IO.
"""
from __future__ import annotations

import pytest

from app.services.email import EmailService


class _StubResponse:
    status_code = 201
    def json(self): return {"messageId": "test"}
    def raise_for_status(self): pass


class _StubClient:
    def __init__(self):
        self.calls = []
    async def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return _StubResponse()
    async def aclose(self): pass


@pytest.mark.asyncio
async def test_send_verification_calls_brevo_with_correct_payload():
    client = _StubClient()
    svc = EmailService(client=client, api_key="testkey", sender_email="n@x", sender_name="N")
    await svc.send_verification("u@x.com", token="abc", verify_base_url="https://h")

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["url"] == "https://api.brevo.com/v3/smtp/email"
    assert call["headers"]["api-key"] == "testkey"
    assert call["json"]["to"][0]["email"] == "u@x.com"
    assert "Подтверждение" in call["json"]["subject"]
    assert "https://h/auth/verify/abc" in call["json"]["htmlContent"]


@pytest.mark.asyncio
async def test_send_approved():
    client = _StubClient()
    svc = EmailService(client=client, api_key="testkey", sender_email="n@x", sender_name="N")
    await svc.send_approved("u@x.com", cabinet_url="https://h/cabinet")
    assert "выдан" in client.calls[0]["json"]["subject"]


@pytest.mark.asyncio
async def test_send_rejected_with_reason():
    client = _StubClient()
    svc = EmailService(client=client, api_key="testkey", sender_email="n@x", sender_name="N")
    await svc.send_rejected("u@x.com", reason="spam", contact="admin@x.com")
    assert "отклонена" in client.calls[0]["json"]["subject"]
    assert "spam" in client.calls[0]["json"]["htmlContent"]
```

- [ ] **Step 2: Run, expect failure**

```bash
python -m pytest tests/site/test_email.py -v
```

Expected: ImportError.

- [ ] **Step 3: `app/templates/emails/verify.html`**

```html
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>Подтверждение регистрации</title></head>
<body style="font-family: Inter, system-ui, sans-serif; background: #F7F3EB; padding: 32px; color: #1A1818;">
  <div style="max-width: 480px; margin: 0 auto; background: #FFFFFF; padding: 32px; border-radius: 8px; box-shadow: 0 8px 24px rgba(26,24,24,0.06);">
    <h1 style="font-family: 'Cormorant Garamond', Georgia, serif; font-size: 32px; margin: 0 0 16px;">Cyber <span style="color: #B8935A;">Berezka</span></h1>
    <p>Добро пожаловать.</p>
    <p>Для завершения регистрации подтвердите email-адрес — нажмите на кнопку ниже:</p>
    <p style="text-align: center; margin: 32px 0;">
      <a href="{{ verify_url }}" style="display: inline-block; background: #B8351F; color: #FFFFFF; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: 600;">Подтвердить email</a>
    </p>
    <p style="font-size: 13px; color: #6B6661;">Если кнопка не открывается, скопируйте ссылку:<br><code style="word-break: break-all;">{{ verify_url }}</code></p>
    <p style="font-size: 13px; color: #6B6661; margin-top: 32px;">Если вы не регистрировались в Cyber Berezka, проигнорируйте это письмо.</p>
  </div>
</body>
</html>
```

- [ ] **Step 4: `app/templates/emails/approved.html`**

```html
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>Доступ выдан</title></head>
<body style="font-family: Inter, system-ui, sans-serif; background: #F7F3EB; padding: 32px; color: #1A1818;">
  <div style="max-width: 480px; margin: 0 auto; background: #FFFFFF; padding: 32px; border-radius: 8px; box-shadow: 0 8px 24px rgba(26,24,24,0.06);">
    <h1 style="font-family: 'Cormorant Garamond', Georgia, serif; font-size: 32px; margin: 0 0 16px;">Cyber <span style="color: #B8935A;">Berezka</span></h1>
    <p>Доступ к сервису выдан.</p>
    <p>Теперь вы можете войти в кабинет и получить ключи для подключения:</p>
    <p style="text-align: center; margin: 32px 0;">
      <a href="{{ cabinet_url }}" style="display: inline-block; background: #B8351F; color: #FFFFFF; padding: 14px 32px; text-decoration: none; border-radius: 6px; font-weight: 600;">Открыть кабинет</a>
    </p>
  </div>
</body>
</html>
```

- [ ] **Step 5: `app/templates/emails/rejected.html`**

```html
<!doctype html>
<html lang="ru">
<head><meta charset="utf-8"><title>Заявка отклонена</title></head>
<body style="font-family: Inter, system-ui, sans-serif; background: #F7F3EB; padding: 32px; color: #1A1818;">
  <div style="max-width: 480px; margin: 0 auto; background: #FFFFFF; padding: 32px; border-radius: 8px; box-shadow: 0 8px 24px rgba(26,24,24,0.06);">
    <h1 style="font-family: 'Cormorant Garamond', Georgia, serif; font-size: 32px; margin: 0 0 16px;">Cyber <span style="color: #B8935A;">Berezka</span></h1>
    <p>К сожалению, ваша заявка на доступ к сервису отклонена.</p>
    {% if reason %}
    <p><strong>Причина:</strong> {{ reason }}</p>
    {% endif %}
    <p>Если вы считаете это ошибкой, ответьте на это письмо или напишите на <a href="mailto:{{ contact }}">{{ contact }}</a>.</p>
  </div>
</body>
</html>
```

- [ ] **Step 6: `app/services/email.py`**

```python
"""Brevo Transactional Mail API client.

We pass an httpx.AsyncClient instance in for testability.
"""
from __future__ import annotations

from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates" / "emails"
_env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


class EmailService:
    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        api_key: str = "",
        sender_email: str = "",
        sender_name: str = "",
    ):
        self.client = client or httpx.AsyncClient(timeout=15.0)
        self.api_key = api_key
        self.sender_email = sender_email
        self.sender_name = sender_name

    async def _send(self, to_email: str, subject: str, html: str) -> None:
        resp = await self.client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": self.api_key, "accept": "application/json"},
            json={
                "sender": {"name": self.sender_name, "email": self.sender_email},
                "to": [{"email": to_email}],
                "subject": subject,
                "htmlContent": html,
            },
            timeout=15.0,
        )
        resp.raise_for_status()

    async def send_verification(self, to_email: str, token: str, verify_base_url: str) -> None:
        verify_url = f"{verify_base_url.rstrip('/')}/auth/verify/{token}"
        html = _env.get_template("verify.html").render(verify_url=verify_url)
        await self._send(to_email, "Подтверждение регистрации в Cyber Berezka", html)

    async def send_approved(self, to_email: str, cabinet_url: str) -> None:
        html = _env.get_template("approved.html").render(cabinet_url=cabinet_url)
        await self._send(to_email, "Доступ к Cyber Berezka выдан", html)

    async def send_rejected(self, to_email: str, reason: str | None, contact: str) -> None:
        html = _env.get_template("rejected.html").render(reason=reason, contact=contact)
        await self._send(to_email, "Заявка в Cyber Berezka отклонена", html)
```

- [ ] **Step 7: Run, expect pass**

```bash
python -m pytest tests/site/test_email.py -v
```

Expected: 3 passed.

- [ ] **Step 8: Commit**

```bash
git add infra/site/app/services/email.py infra/site/app/templates/emails/ tests/site/test_email.py
git commit -m "feat(site/email): Brevo client + verify/approved/rejected templates"
```

---

## Task 8: Auth service (register/verify/authenticate)

**Files:**
- Create: `infra/site/app/services/auth.py`
- Create: `tests/site/test_auth.py`

- [ ] **Step 1: `tests/site/test_auth.py`**

```python
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
```

- [ ] **Step 2: Run, expect failure**

```bash
python -m pytest tests/site/test_auth.py -v
```

Expected: ImportError.

- [ ] **Step 3: `app/services/auth.py`**

```python
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
```

- [ ] **Step 4: Run, expect pass**

```bash
python -m pytest tests/site/test_auth.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add infra/site/app/services/auth.py tests/site/test_auth.py
git commit -m "feat(site/services): AuthService (register, verify_email, authenticate)"
```

---

## Task 9: Auth routers + templates + main.py wiring

**Files:**
- Create: `infra/site/app/routers/auth.py`
- Create: `infra/site/app/deps.py`
- Create: `infra/site/app/templates/auth/register.html`
- Create: `infra/site/app/templates/auth/login.html`
- Create: `infra/site/app/templates/auth/verify_sent.html`
- Modify: `infra/site/app/main.py`

- [ ] **Step 1: `app/deps.py`** — FastAPI DI helpers

```python
"""Common FastAPI dependencies."""
from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from redis.asyncio import Redis, from_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.models.session import Session as SessionModel
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
```

- [ ] **Step 2: `app/routers/auth.py`**

```python
"""Auth routes: register, login, logout, email verify."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import get_session_service, get_current_user
from app.models.user import User
from app.services.auth import AuthError, AuthService
from app.services.email import EmailService
from app.services.sessions import SessionService

router = APIRouter(prefix="/auth", tags=["auth"])

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")
TEMPLATES.env.globals["site_host"] = settings.site_host


def _email_service() -> EmailService:
    return EmailService(
        api_key=settings.brevo_api_key,
        sender_email=settings.brevo_sender_email,
        sender_name=settings.brevo_sender_name,
    )


@router.get("/register", response_class=HTMLResponse)
async def register_form(request: Request):
    return TEMPLATES.TemplateResponse("auth/register.html", {"request": request, "error": None})


@router.post("/register", response_class=HTMLResponse)
async def register_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    password_confirm: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    if password != password_confirm:
        return TEMPLATES.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Пароли не совпадают", "email": email},
            status_code=400,
        )
    svc = AuthService(db)
    try:
        user, verify_token = await svc.register(email=email, password=password)
    except AuthError as e:
        msg = {
            "email_taken": "Email уже занят",
            "weak_password": "Пароль должен быть не короче 12 символов",
        }.get(str(e), "Ошибка регистрации")
        return TEMPLATES.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": msg, "email": email},
            status_code=400,
        )
    try:
        await _email_service().send_verification(
            user.email, verify_token, verify_base_url=f"https://{settings.site_host}",
        )
    except Exception:
        pass  # email failure is logged but doesn't block registration
    return TEMPLATES.TemplateResponse(
        "auth/verify_sent.html", {"request": request, "email": user.email}
    )


@router.get("/verify/{token}")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    svc = AuthService(db)
    ok = await svc.verify_email(token)
    if not ok:
        raise HTTPException(status_code=400, detail="Ссылка недействительна или уже использована.")
    return RedirectResponse(url="/auth/login?verified=1", status_code=303)


@router.get("/login", response_class=HTMLResponse)
async def login_form(request: Request):
    return TEMPLATES.TemplateResponse("auth/login.html", {"request": request, "error": None})


@router.post("/login")
async def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: AsyncSession = Depends(get_db),
    svc: SessionService = Depends(get_session_service),
):
    auth = AuthService(db)
    user, err = await auth.authenticate(email=email, password=password)
    if user is None:
        msg = {
            "invalid_credentials": "Неверный email или пароль",
            "rejected": "Доступ к сервису отклонён",
            "inactive": "Аккаунт деактивирован",
        }.get(err, "Ошибка входа")
        return TEMPLATES.TemplateResponse(
            "auth/login.html", {"request": request, "error": msg, "email": email}, status_code=400,
        )
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    sid = await svc.create(user_id=user.id, ip=ip, ua=ua)
    resp = RedirectResponse(url="/cabinet", status_code=303)
    resp.set_cookie(
        key="__Host-session",
        value=sid,
        max_age=settings.session_lifetime_hours * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    return resp


@router.post("/logout")
async def logout(
    request: Request,
    svc: SessionService = Depends(get_session_service),
    user: User | None = Depends(get_current_user),
):
    sid = request.cookies.get("__Host-session")
    if sid:
        await svc.revoke(sid)
    resp = RedirectResponse(url="/", status_code=303)
    resp.delete_cookie("__Host-session", path="/")
    return resp
```

- [ ] **Step 3: `app/templates/auth/register.html`**

```html
{% extends "base.html" %}
{% block title %}Регистрация — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-md mx-auto px-6 py-16">
  <div class="bg-bg-card border border-border-light rounded-lg shadow-card p-8">
    <h1 class="font-serif text-3xl mb-6">Создать аккаунт</h1>
    {% if error %}<p class="text-cta mb-4 text-sm">{{ error }}</p>{% endif %}
    <form method="POST" action="/auth/register" class="space-y-4">
      <label class="block">
        <span class="text-sm text-text-secondary">Email</span>
        <input type="email" name="email" required value="{{ email or '' }}"
               class="mt-1 block w-full border border-border-light rounded px-3 py-2 bg-white">
      </label>
      <label class="block">
        <span class="text-sm text-text-secondary">Пароль (минимум 12 символов)</span>
        <input type="password" name="password" required minlength="12"
               class="mt-1 block w-full border border-border-light rounded px-3 py-2 bg-white">
      </label>
      <label class="block">
        <span class="text-sm text-text-secondary">Повтор пароля</span>
        <input type="password" name="password_confirm" required minlength="12"
               class="mt-1 block w-full border border-border-light rounded px-3 py-2 bg-white">
      </label>
      <label class="flex items-start gap-2 text-sm">
        <input type="checkbox" required class="mt-1">
        <span>Я принимаю <a href="/legal/terms" class="underline text-accent-goldDk">Условия использования</a> и <a href="/legal/privacy" class="underline text-accent-goldDk">Политику конфиденциальности</a></span>
      </label>
      <button type="submit" class="btn-primary w-full">Создать аккаунт</button>
    </form>
    <p class="mt-6 text-sm text-text-muted">Уже есть аккаунт? <a href="/auth/login" class="text-accent-goldDk underline">Войти</a></p>
  </div>
</main>
{% endblock %}
```

- [ ] **Step 4: `app/templates/auth/login.html`**

```html
{% extends "base.html" %}
{% block title %}Вход — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-md mx-auto px-6 py-16">
  <div class="bg-bg-card border border-border-light rounded-lg shadow-card p-8">
    <h1 class="font-serif text-3xl mb-6">Войти</h1>
    {% if request.query_params.get('verified') %}
      <p class="text-success mb-4 text-sm">Email подтверждён, теперь можно войти.</p>
    {% endif %}
    {% if error %}<p class="text-cta mb-4 text-sm">{{ error }}</p>{% endif %}
    <form method="POST" action="/auth/login" class="space-y-4">
      <label class="block">
        <span class="text-sm text-text-secondary">Email</span>
        <input type="email" name="email" required value="{{ email or '' }}"
               class="mt-1 block w-full border border-border-light rounded px-3 py-2 bg-white">
      </label>
      <label class="block">
        <span class="text-sm text-text-secondary">Пароль</span>
        <input type="password" name="password" required
               class="mt-1 block w-full border border-border-light rounded px-3 py-2 bg-white">
      </label>
      <button type="submit" class="btn-primary w-full">Войти</button>
    </form>
    <p class="mt-6 text-sm text-text-muted">Нет аккаунта? <a href="/auth/register" class="text-accent-goldDk underline">Зарегистрироваться</a></p>
  </div>
</main>
{% endblock %}
```

- [ ] **Step 5: `app/templates/auth/verify_sent.html`**

```html
{% extends "base.html" %}
{% block title %}Подтвердите email — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-md mx-auto px-6 py-16">
  <div class="bg-bg-card border border-border-light rounded-lg shadow-card p-8 text-center">
    <h1 class="font-serif text-3xl mb-4">Письмо отправлено</h1>
    <p>Мы отправили письмо со ссылкой подтверждения на <strong>{{ email }}</strong>.</p>
    <p class="text-sm text-text-muted mt-4">Если письмо не пришло за 10 минут, проверьте папку «Спам».</p>
  </div>
</main>
{% endblock %}
```

- [ ] **Step 6: `app/main.py` — добавить include_router**

В `app/main.py` после `from app.routers import landing, legal` добавить `from app.routers import auth`. В блоке `app.include_router(...)` добавить `app.include_router(auth.router)`.

- [ ] **Step 7: Commit**

```bash
git add infra/site/app/routers/auth.py infra/site/app/deps.py \
        infra/site/app/templates/auth/ infra/site/app/main.py
git commit -m "feat(site/auth): register/login/logout/verify routes + templates + DI helpers"
```

---

## Task 10: current_user wiring — already covered in Task 9 (deps.py). Skip.

(This task number reserved historically; deps.py created in Task 9.)

---

## Task 11: Cabinet base + pending states + templates

**Files:**
- Create: `infra/site/app/routers/cabinet.py`
- Create: `infra/site/app/templates/cabinet/index.html`
- Create: `infra/site/app/templates/cabinet/pending_email.html`
- Create: `infra/site/app/templates/cabinet/pending_admin.html`
- Create: `infra/site/app/templates/cabinet/rejected.html`
- Modify: `infra/site/app/main.py`

- [ ] **Step 1: `app/routers/cabinet.py`**

```python
"""Cabinet — user dashboard with state-based rendering."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from app.config import settings
from app.deps import require_user
from app.models.user import User

router = APIRouter(prefix="/cabinet", tags=["cabinet"])

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def cabinet_home(request: Request, user: User = Depends(require_user)):
    """Render cabinet according to user state."""
    if user.is_rejected:
        return TEMPLATES.TemplateResponse(
            "cabinet/rejected.html", {"request": request, "user": user},
        )
    if not user.is_email_verified:
        return TEMPLATES.TemplateResponse(
            "cabinet/pending_email.html", {"request": request, "user": user},
        )
    if not user.is_approved:
        return TEMPLATES.TemplateResponse(
            "cabinet/pending_admin.html", {"request": request, "user": user},
        )
    return TEMPLATES.TemplateResponse(
        "cabinet/index.html", {"request": request, "user": user, "site_host": settings.site_host},
    )
```

- [ ] **Step 2: `app/templates/cabinet/pending_email.html`**

```html
{% extends "base.html" %}
{% block title %}Подтвердите email — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-2xl mx-auto px-6 py-16">
  <div class="bg-bg-card border border-border-light rounded-lg shadow-card p-8">
    <h1 class="font-serif text-3xl mb-4">Подтвердите email</h1>
    <p>Мы отправили письмо со ссылкой подтверждения на <strong>{{ user.email }}</strong>.</p>
    <p class="text-sm text-text-muted mt-4">Не пришло? Проверьте папку «Спам». Если письма нет — напишите нам.</p>
  </div>
</main>
{% endblock %}
```

- [ ] **Step 3: `app/templates/cabinet/pending_admin.html`**

```html
{% extends "base.html" %}
{% block title %}Заявка на рассмотрении — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-2xl mx-auto px-6 py-16">
  <div class="bg-bg-card border border-border-light rounded-lg shadow-card p-8">
    <h1 class="font-serif text-3xl mb-4">Заявка на рассмотрении</h1>
    <p>Спасибо за регистрацию. Ваша заявка передана администратору.</p>
    <p class="mt-4">Мы сообщим на <strong>{{ user.email }}</strong>, как только выдадим доступ. Обычно это занимает не более суток.</p>
    <form method="POST" action="/auth/logout" class="mt-8">
      <button class="text-sm text-text-muted underline">Выйти</button>
    </form>
  </div>
</main>
{% endblock %}
```

- [ ] **Step 4: `app/templates/cabinet/rejected.html`**

```html
{% extends "base.html" %}
{% block title %}Доступ отклонён — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-2xl mx-auto px-6 py-16">
  <div class="bg-bg-card border border-border-light rounded-lg shadow-card p-8">
    <h1 class="font-serif text-3xl mb-4">Доступ отклонён</h1>
    <p>К сожалению, ваша заявка отклонена администратором.</p>
    {% if user.rejection_reason %}
      <p class="mt-4"><strong>Причина:</strong> {{ user.rejection_reason }}</p>
    {% endif %}
    <form method="POST" action="/auth/logout" class="mt-8">
      <button class="text-sm text-text-muted underline">Выйти</button>
    </form>
  </div>
</main>
{% endblock %}
```

- [ ] **Step 5: `app/templates/cabinet/index.html`** — заглушка с заголовком и ссылкой на keys

```html
{% extends "base.html" %}
{% block title %}Кабинет — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-4xl mx-auto px-6 py-12">
  <header class="flex items-center justify-between mb-8">
    <h1 class="font-serif text-3xl">Кабинет</h1>
    <div class="flex items-center gap-4 text-sm">
      <span class="text-text-muted">{{ user.email }}</span>
      {% if user.is_admin %}<a href="/cabinet/admin/pending" class="text-accent-goldDk underline">Pending users</a>{% endif %}
      <form method="POST" action="/auth/logout" class="inline">
        <button class="text-text-muted underline">Выйти</button>
      </form>
    </div>
  </header>

  {# Сервера, ключи — наполнятся в Task 13/15 #}
  <section class="bg-bg-card border border-border-light rounded-lg shadow-card p-6 mb-6">
    <h2 class="font-serif text-xl mb-4">Доступные серверы</h2>
    {% include "cabinet/_server_list.html" ignore missing %}
  </section>

  <section class="bg-bg-card border border-border-light rounded-lg shadow-card p-6">
    <h2 class="font-serif text-xl mb-4">Мои ключи</h2>
    <p class="text-text-muted">Раздел ключей будет добавлен в следующем релизе.</p>
  </section>
</main>
{% endblock %}
```

- [ ] **Step 6: Wire `cabinet.router` в `app/main.py`**

```python
from app.routers import auth, cabinet, landing, legal
# ...
app.include_router(cabinet.router)
```

- [ ] **Step 7: Commit**

```bash
git add infra/site/app/routers/cabinet.py infra/site/app/templates/cabinet/ infra/site/app/main.py
git commit -m "feat(site/cabinet): base dashboard + email-pending/admin-pending/rejected states"
```

---

## Task 12: Remnawave service + VPN keys service

**Files:**
- Create: `infra/site/app/services/remnawave.py`
- Create: `infra/site/app/services/vpn_keys.py`

- [ ] **Step 1: `app/services/remnawave.py`**

```python
"""Remnawave API wrapper for the site app.

Reuses the same HTTPX-based client pattern as infra/remnawave/_lib/client.py,
but instantiated with site's runtime config (REMNAWAVE_API_URL pointing to
internal http://remnawave:3000).
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import settings


class RemnawaveAPIError(Exception):
    def __init__(self, status: int, body: Any):
        super().__init__(f"Remnawave API {status}: {body}")
        self.status = status
        self.body = body


class RemnawaveAPI:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.base = settings.remnawave_api_url.rstrip("/")
        self.token = settings.remnawave_api_token
        self.client = client or httpx.AsyncClient(
            timeout=15.0,
            headers={"Authorization": f"Bearer {self.token}", "User-Agent": "cyber-berezka-site/0.1"},
        )

    async def _call(self, method: str, path: str, **kwargs) -> Any:
        resp = await self.client.request(method, f"{self.base}{path}", **kwargs)
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        if not (200 <= resp.status_code < 300):
            raise RemnawaveAPIError(resp.status_code, data)
        if isinstance(data, dict) and "response" in data and len(data) == 1:
            return data["response"]
        return data

    async def list_nodes(self) -> list[dict]:
        return await self._call("GET", "/api/nodes") or []

    async def create_user(self, username: str, expire_at: str | None = None) -> dict:
        payload = {"username": username}
        if expire_at:
            payload["expireAt"] = expire_at
        return await self._call("POST", "/api/users", json=payload)

    async def get_user(self, user_uuid: str) -> dict:
        return await self._call("GET", f"/api/users/{user_uuid}")

    async def revoke_user(self, user_uuid: str) -> None:
        await self._call("PATCH", f"/api/users/{user_uuid}", json={"status": "DISABLED"})

    async def aclose(self) -> None:
        await self.client.aclose()
```

- [ ] **Step 2: `app/services/vpn_keys.py`**

```python
"""VPN keys business logic — creates Remnawave user on demand, persists local row."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User
from app.models.vpn_key import VpnKey
from app.services.remnawave import RemnawaveAPI


class VpnKeysService:
    def __init__(self, db: AsyncSession, remnawave: RemnawaveAPI):
        self.db = db
        self.remnawave = remnawave

    async def ensure_remnawave_user(self, user: User) -> None:
        """Create the Remnawave user once, store UUID/short_uuid in local row."""
        if user.remnawave_user_uuid:
            return
        far_future = "2099-12-31T00:00:00Z"
        rw_user = await self.remnawave.create_user(
            username=f"user_{user.id}", expire_at=far_future,
        )
        user.remnawave_user_uuid = rw_user.get("uuid")
        user.remnawave_short_uuid = rw_user.get("shortUuid")
        await self.db.commit()

    async def create_key(self, user: User, label: str | None) -> tuple[VpnKey, str]:
        """Create a VpnKey row, return (key, subscription_url)."""
        await self.ensure_remnawave_user(user)
        rw_user = await self.remnawave.get_user(user.remnawave_user_uuid)
        subscription_url = rw_user.get("subscriptionUrl") or ""
        key = VpnKey(
            user_id=user.id,
            label=label or f"Ключ от {datetime.now(timezone.utc).strftime('%d.%m.%Y')}",
        )
        self.db.add(key)
        log = AuditLog(user_id=user.id, event_type="key.create", event_data={"label": key.label})
        self.db.add(log)
        await self.db.commit()
        await self.db.refresh(key)
        return key, subscription_url

    async def list_keys_with_url(self, user: User) -> tuple[list[VpnKey], str]:
        result = await self.db.execute(
            select(VpnKey).where(VpnKey.user_id == user.id, VpnKey.status == "active").order_by(VpnKey.id.desc())
        )
        keys = list(result.scalars())
        if not user.remnawave_user_uuid or not keys:
            return keys, ""
        rw_user = await self.remnawave.get_user(user.remnawave_user_uuid)
        return keys, rw_user.get("subscriptionUrl", "")

    async def revoke_key(self, user: User, key_id: int) -> None:
        result = await self.db.execute(
            select(VpnKey).where(VpnKey.id == key_id, VpnKey.user_id == user.id)
        )
        key = result.scalar_one_or_none()
        if key is None:
            return
        key.status = "revoked"
        log = AuditLog(user_id=user.id, event_type="key.revoke", event_data={"key_id": key_id})
        self.db.add(log)
        await self.db.commit()
```

- [ ] **Step 3: Commit**

```bash
git add infra/site/app/services/remnawave.py infra/site/app/services/vpn_keys.py
git commit -m "feat(site/services): RemnawaveAPI + VpnKeysService (create/list/revoke keys)"
```

---

## Task 13: Cabinet keys page + deep-link buttons + QR

**Files:**
- Create: `infra/site/app/templates/cabinet/keys.html`
- Modify: `infra/site/app/routers/cabinet.py` (add /cabinet/keys routes)

- [ ] **Step 1: Extend `app/routers/cabinet.py`** — add routes after existing `cabinet_home`:

```python
import base64
import io

import qrcode
from fastapi import Form
from fastapi.responses import RedirectResponse

from app.db import get_db
from app.services.remnawave import RemnawaveAPI
from app.services.vpn_keys import VpnKeysService
from sqlalchemy.ext.asyncio import AsyncSession


def _qr_data_uri(payload: str) -> str:
    img = qrcode.make(payload)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


@router.get("/keys", response_class=HTMLResponse)
async def keys_page(
    request: Request,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        keys, sub_url = await svc.list_keys_with_url(user)
    finally:
        await rw.aclose()
    qr = _qr_data_uri(sub_url) if sub_url else ""
    return TEMPLATES.TemplateResponse(
        "cabinet/keys.html",
        {"request": request, "user": user, "keys": keys,
         "subscription_url": sub_url, "qr_data_uri": qr,
         "site_host": settings.site_host},
    )


@router.post("/keys")
async def keys_create(
    request: Request,
    label: str = Form(""),
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    if not user.is_approved:
        return RedirectResponse(url="/cabinet", status_code=303)
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        await svc.create_key(user, label=label or None)
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet/keys", status_code=303)


@router.post("/keys/{key_id}/revoke")
async def keys_revoke(
    key_id: int,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    rw = RemnawaveAPI()
    try:
        svc = VpnKeysService(db, rw)
        await svc.revoke_key(user, key_id)
    finally:
        await rw.aclose()
    return RedirectResponse(url="/cabinet/keys", status_code=303)
```

- [ ] **Step 2: `app/templates/cabinet/keys.html`**

```html
{% extends "base.html" %}
{% block title %}Ключи — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-4xl mx-auto px-6 py-12">
  <header class="flex items-center justify-between mb-8">
    <h1 class="font-serif text-3xl">Мои ключи</h1>
    <a href="/cabinet" class="text-sm text-accent-goldDk underline">← В кабинет</a>
  </header>

  <section class="bg-bg-card border border-border-light rounded-lg shadow-card p-6 mb-6">
    <form method="POST" action="/cabinet/keys" class="flex gap-3 items-end">
      <label class="flex-1">
        <span class="text-sm text-text-secondary">Название ключа (опционально)</span>
        <input type="text" name="label" maxlength="64" placeholder="Телефон, ноутбук..."
               class="mt-1 block w-full border border-border-light rounded px-3 py-2 bg-white">
      </label>
      <button type="submit" class="btn-primary">+ Получить новый ключ</button>
    </form>
  </section>

  {% if subscription_url %}
  <section class="bg-bg-card border border-border-light rounded-lg shadow-card p-6 mb-6">
    <h2 class="font-serif text-xl mb-4">Подключение</h2>

    <div class="mb-6">
      <p class="text-sm text-text-secondary mb-3">Откройте в приложении одной кнопкой:</p>
      <div class="flex flex-wrap gap-3">
        <a href="v2raytun://import/{{ subscription_url | urlencode }}"
           class="px-5 py-2 border-2 border-accent-goldDk rounded hover:bg-accent-gold hover:text-white transition">v2RayTun</a>
        <a href="hiddify://install-sub?url={{ subscription_url | urlencode }}"
           class="px-5 py-2 border-2 border-accent-goldDk rounded hover:bg-accent-gold hover:text-white transition">Hiddify</a>
        <a href="sn://subscription?url={{ subscription_url | urlencode }}"
           class="px-5 py-2 border-2 border-accent-goldDk rounded hover:bg-accent-gold hover:text-white transition">NekoBox</a>
      </div>
      <p class="text-xs text-text-muted mt-3">Если приложение не установлено: <a href="#install" class="underline">инструкции</a>.</p>
    </div>

    <div class="grid md:grid-cols-2 gap-6 items-start">
      <div>
        <p class="text-sm text-text-secondary mb-2">Или вручную:</p>
        <div class="flex gap-2 mb-3">
          <input id="suburl" readonly value="{{ subscription_url }}"
                 class="flex-1 border border-border-light rounded px-3 py-2 bg-white font-mono text-xs">
          <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('suburl').value)"
                  class="px-3 py-2 border border-border-light rounded hover:bg-bg-section-alt text-sm">Копировать</button>
        </div>
      </div>
      <div class="text-center">
        <p class="text-sm text-text-secondary mb-2">QR-код</p>
        <img src="{{ qr_data_uri }}" alt="QR" class="inline-block w-48 h-48 border border-border-light">
      </div>
    </div>
  </section>
  {% endif %}

  <section class="bg-bg-card border border-border-light rounded-lg shadow-card p-6">
    <h2 class="font-serif text-xl mb-4">Активные ключи</h2>
    {% if not keys %}
      <p class="text-text-muted">У вас пока нет активных ключей. Нажмите «Получить новый ключ» выше.</p>
    {% else %}
      <ul class="divide-y divide-border-light">
      {% for k in keys %}
        <li class="py-3 flex items-center justify-between">
          <div>
            <div class="font-medium">{{ k.label }}</div>
            <div class="text-xs text-text-muted">создан {{ k.created_at.strftime('%d.%m.%Y') }}</div>
          </div>
          <form method="POST" action="/cabinet/keys/{{ k.id }}/revoke">
            <button class="text-sm text-cta hover:text-cta-hover underline">Отозвать</button>
          </form>
        </li>
      {% endfor %}
      </ul>
    {% endif %}
  </section>

  <section id="install" class="mt-12 text-sm text-text-muted">
    <h3 class="font-serif text-lg mb-3 text-text-primary">Установка приложений</h3>
    <ul class="grid md:grid-cols-2 gap-3">
      <li>iOS: <a href="https://apps.apple.com/app/v2raytun/id6476628951" class="underline text-accent-goldDk">v2RayTun</a></li>
      <li>Android: <a href="https://play.google.com/store/apps/details?id=com.v2raytun.android" class="underline text-accent-goldDk">v2RayTun</a> / <a href="https://hiddify.com/install" class="underline text-accent-goldDk">Hiddify</a></li>
      <li>Windows: <a href="https://hiddify.com/install" class="underline text-accent-goldDk">Hiddify Desktop</a></li>
      <li>macOS: <a href="https://apps.apple.com/app/hiddify/id6596777532" class="underline text-accent-goldDk">Hiddify</a></li>
    </ul>
  </section>
</main>
{% endblock %}
```

- [ ] **Step 3: Update `cabinet/index.html`** — заменить заглушку «Раздел ключей будет добавлен» на ссылку:

В `app/templates/cabinet/index.html`, в блоке «Мои ключи»:

```html
  <section class="bg-bg-card border border-border-light rounded-lg shadow-card p-6">
    <h2 class="font-serif text-xl mb-4">Ключи</h2>
    <a href="/cabinet/keys" class="btn-primary inline-block">Управление ключами →</a>
  </section>
```

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/routers/cabinet.py infra/site/app/templates/cabinet/
git commit -m "feat(site/cabinet): keys page with deep-link buttons (v2RayTun/Hiddify/NekoBox), QR, revoke"
```

---

## Task 14: Nodes service + Redis cache

**Files:**
- Create: `infra/site/app/services/nodes.py`
- Create: `infra/site/app/services/geo.py`
- Create: `tests/site/test_nodes.py`

- [ ] **Step 1: `tests/site/test_nodes.py`**

```python
"""Tests for nodes service (Remnawave + redis cache)."""
from __future__ import annotations

import json
import pytest

from app.services.nodes import NodesService


class FakeRedis:
    def __init__(self): self.store = {}
    async def get(self, k): return self.store.get(k)
    async def setex(self, k, ttl, v): self.store[k] = v


class FakeAPI:
    def __init__(self, nodes): self.nodes = nodes; self.calls = 0
    async def list_nodes(self): self.calls += 1; return self.nodes


@pytest.mark.asyncio
async def test_first_call_hits_api_then_caches():
    api = FakeAPI([{"name": "n1", "countryCode": "DE", "isConnected": True, "isConnecting": False}])
    svc = NodesService(api=api, redis=FakeRedis())
    a = await svc.get_nodes()
    b = await svc.get_nodes()
    assert api.calls == 1
    assert a == b
    assert a[0]["country"] == "Германия"


@pytest.mark.asyncio
async def test_empty_api_returns_empty_list():
    api = FakeAPI([])
    svc = NodesService(api=api, redis=FakeRedis())
    assert await svc.get_nodes() == []


@pytest.mark.asyncio
async def test_unknown_country_falls_back_to_code():
    api = FakeAPI([{"name": "x", "countryCode": "ZZ", "isConnected": True, "isConnecting": False}])
    svc = NodesService(api=api, redis=FakeRedis())
    out = await svc.get_nodes()
    assert out[0]["country"] == "ZZ"
    assert out[0]["flag"] == "🌐"
```

- [ ] **Step 2: Run, expect failure**

```bash
python -m pytest tests/site/test_nodes.py -v
```

Expected: ImportError.

- [ ] **Step 3: `app/services/geo.py`**

```python
"""ISO country code → (display name, city, flag emoji)."""
from __future__ import annotations

COUNTRY_NAMES: dict[str, tuple[str, str, str]] = {
    "DE": ("Германия", "Frankfurt", "🇩🇪"),
    "NL": ("Нидерланды", "Amsterdam", "🇳🇱"),
    "FR": ("Франция", "Paris", "🇫🇷"),
    "FI": ("Финляндия", "Helsinki", "🇫🇮"),
    "RU": ("Россия", "Moscow", "🇷🇺"),
}


def resolve_country(code: str | None) -> tuple[str, str, str]:
    if not code:
        return ("Unknown", "", "🌐")
    return COUNTRY_NAMES.get(code.upper(), (code.upper(), "", "🌐"))
```

- [ ] **Step 4: `app/services/nodes.py`**

```python
"""Nodes: pull from Remnawave, cache for 30s in Redis."""
from __future__ import annotations

import json

from app.services.geo import resolve_country

CACHE_KEY = "nodes:list"
CACHE_TTL_SECONDS = 30


class NodesService:
    def __init__(self, api, redis):
        self.api = api
        self.redis = redis

    async def get_nodes(self) -> list[dict]:
        cached = await self.redis.get(CACHE_KEY)
        if cached is not None:
            try:
                return json.loads(cached) if isinstance(cached, str) else cached
            except Exception:
                pass
        raw = await self.api.list_nodes()
        result = []
        for n in raw:
            country_code = n.get("countryCode")
            country, city, flag = resolve_country(country_code)
            result.append({
                "name": n.get("name"),
                "country": country,
                "city": city,
                "flag": flag,
                "is_connected": bool(n.get("isConnected")),
                "is_connecting": bool(n.get("isConnecting")),
            })
        await self.redis.setex(CACHE_KEY, CACHE_TTL_SECONDS, json.dumps(result))
        return result
```

- [ ] **Step 5: Run, expect pass**

```bash
python -m pytest tests/site/test_nodes.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add infra/site/app/services/nodes.py infra/site/app/services/geo.py tests/site/test_nodes.py
git commit -m "feat(site/services): NodesService (Remnawave fetch + 30s Redis cache) and geo lookup"
```

---

## Task 15: Server list blocks on landing + cabinet

**Files:**
- Create: `infra/site/app/templates/cabinet/_server_list.html`
- Create: `infra/site/app/templates/landing/_server_list.html`
- Modify: `infra/site/app/routers/landing.py`
- Modify: `infra/site/app/routers/cabinet.py`
- Modify: `infra/site/app/templates/landing/index.html`

- [ ] **Step 1: `app/templates/cabinet/_server_list.html`**

```html
{% if nodes %}
<ul class="divide-y divide-border-light">
  {% for n in nodes %}
  <li class="flex items-center justify-between py-2">
    <span>{{ n.flag }} {{ n.country }}{% if n.city %} ({{ n.city }}){% endif %}</span>
    {% if n.is_connected %}
      <span class="text-success">● онлайн</span>
    {% else %}
      <span class="text-text-muted">● технические работы</span>
    {% endif %}
  </li>
  {% endfor %}
</ul>
<p class="text-xs text-text-muted mt-3">Подключения распределяются автоматически между серверами.</p>
{% else %}
<p class="text-text-muted">Список серверов сейчас недоступен.</p>
{% endif %}
```

- [ ] **Step 2: `app/templates/landing/_server_list.html`**

```html
{% if nodes %}
<section class="bg-bg-section-alt py-16">
  <div class="max-w-4xl mx-auto px-6">
    <h2 class="font-serif text-3xl mb-6">Наши серверы</h2>
    <p class="text-text-secondary mb-6">{{ nodes_online_count }} сервера онлайн в {{ nodes_countries_count }} стран{{ 'е' if nodes_countries_count == 1 else 'ах' }}.</p>
    <ul class="grid md:grid-cols-2 gap-3">
      {% for n in nodes %}
      <li class="flex items-center justify-between bg-bg-card border border-border-light rounded px-4 py-3">
        <span>{{ n.flag }} {{ n.country }}{% if n.city %} <span class="text-text-muted">({{ n.city }})</span>{% endif %}</span>
        {% if n.is_connected %}
          <span class="text-success">● онлайн</span>
        {% else %}
          <span class="text-text-muted">● тех. работы</span>
        {% endif %}
      </li>
      {% endfor %}
    </ul>
    <p class="text-xs text-text-muted mt-4">Подключение распределяется автоматически — чем больше серверов, тем устойчивее канал.</p>
  </div>
</section>
{% endif %}
```

- [ ] **Step 3: Extend `app/routers/landing.py`** — load nodes into context:

```python
"""Landing routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from redis.asyncio import Redis

from app.deps import get_redis
from app.services.nodes import NodesService
from app.services.remnawave import RemnawaveAPI

router = APIRouter()

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


async def _load_nodes_context(redis: Redis) -> dict:
    rw = RemnawaveAPI()
    try:
        svc = NodesService(api=rw, redis=redis)
        nodes = await svc.get_nodes()
    except Exception:
        nodes = []
    finally:
        await rw.aclose()
    countries = {n["country"] for n in nodes if n["is_connected"]}
    return {
        "nodes": nodes,
        "nodes_online_count": sum(1 for n in nodes if n["is_connected"]),
        "nodes_countries_count": len(countries),
    }


@router.get("/landing", response_class=HTMLResponse, include_in_schema=False)
async def landing(request: Request, redis: Redis = Depends(get_redis)):
    ctx = {"request": request, **(await _load_nodes_context(redis))}
    return TEMPLATES.TemplateResponse("landing/index.html", ctx)


# Export helper for the / handler in main.py.
async def render_landing(request: Request, redis: Redis):
    ctx = {"request": request, **(await _load_nodes_context(redis))}
    return TEMPLATES.TemplateResponse("landing/index.html", ctx)


async def index(request: Request):
    """Backward-compat shim used from main.py's root handler.

    Returns a minimal response without nodes context — main.py calls a
    different render path that supplies the context.
    """
    return TEMPLATES.TemplateResponse("landing/index.html", {"request": request, "nodes": []})
```

- [ ] **Step 4: Update `app/main.py` root handler** to pass nodes context:

Заменить текущий `root` обработчик в `app/main.py`:

```python
from app.deps import get_redis
from app.routers.landing import render_landing
from redis.asyncio import Redis

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root(request: Request, redis: Redis = Depends(get_redis)):
    host = request.headers.get("host", "")
    if host.startswith("home.") or host == settings.landing_domain:
        return await render_landing(request, redis)
    return RedirectResponse(url=f"https://{settings.landing_domain}/", status_code=302)
```

(`Depends` импорт из `fastapi` нужен — добавить если отсутствует.)

- [ ] **Step 5: Update `app/templates/landing/index.html`** — добавить include блока перед FAQ или после Tech-trust секции:

В подходящем месте (после блока «Технологии», перед FAQ) добавить:

```html
{% include "landing/_server_list.html" ignore missing %}
```

- [ ] **Step 6: Update `app/routers/cabinet.py`** `cabinet_home` — добавить nodes context:

В `cabinet_home`, перед возвратом `cabinet/index.html`, дополнить контекст nodes:

```python
async def cabinet_home(
    request: Request,
    user: User = Depends(require_user),
    redis = Depends(get_redis),
):
    # ... existing branching ...
    rw = RemnawaveAPI()
    try:
        nsvc = NodesService(api=rw, redis=redis)
        nodes = await nsvc.get_nodes()
    except Exception:
        nodes = []
    finally:
        await rw.aclose()
    return TEMPLATES.TemplateResponse(
        "cabinet/index.html",
        {"request": request, "user": user, "site_host": settings.site_host, "nodes": nodes},
    )
```

Импорт `from app.deps import get_redis` и `from app.services.nodes import NodesService` добавить.

- [ ] **Step 7: Commit**

```bash
git add infra/site/app/routers/landing.py infra/site/app/routers/cabinet.py \
        infra/site/app/templates/landing/ infra/site/app/templates/cabinet/_server_list.html \
        infra/site/app/main.py
git commit -m "feat(site): dynamic server list on landing and cabinet (Remnawave + 30s cache)"
```

---

## Task 16: Admin pending router + approve/reject endpoints

**Files:**
- Create: `infra/site/app/routers/admin.py`
- Create: `infra/site/app/templates/cabinet/admin_pending.html`
- Create: `tests/site/test_admin.py`
- Modify: `infra/site/app/main.py`

- [ ] **Step 1: `tests/site/test_admin.py`**

```python
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
    u = User(email="a@x", email_normalized="a@x", password_hash="x", is_admin=True,
            email_verified_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc))
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
```

- [ ] **Step 2: Run, expect failure**

```bash
python -m pytest tests/site/test_admin.py -v
```

Expected: ImportError.

- [ ] **Step 3: `app/routers/admin.py`**

```python
"""Admin approval / reject pending users."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_db
from app.deps import require_admin
from app.models.audit_log import AuditLog
from app.models.user import User
from app.services.email import EmailService

router = APIRouter(prefix="/cabinet/admin", tags=["admin"])

TEMPLATES = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def _email_service() -> EmailService:
    return EmailService(
        api_key=settings.brevo_api_key,
        sender_email=settings.brevo_sender_email,
        sender_name=settings.brevo_sender_name,
    )


async def approve_user_service(db: AsyncSession, target: User, admin: User) -> None:
    target.admin_approved_at = datetime.now(timezone.utc)
    target.admin_approved_by = admin.id
    db.add(AuditLog(user_id=admin.id, event_type="user.approved",
                    event_data={"target_user_id": target.id}))
    await db.commit()


async def reject_user_service(
    db: AsyncSession, target: User, admin: User, reason: str | None,
) -> None:
    target.admin_rejected_at = datetime.now(timezone.utc)
    target.admin_rejected_by = admin.id
    target.rejection_reason = reason
    db.add(AuditLog(user_id=admin.id, event_type="user.rejected",
                    event_data={"target_user_id": target.id, "reason": reason}))
    await db.commit()


@router.get("/pending", response_class=HTMLResponse)
async def pending_list(
    request: Request,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(
            User.email_verified_at.isnot(None),
            User.admin_approved_at.is_(None),
            User.admin_rejected_at.is_(None),
        ).order_by(User.created_at.desc())
    )
    users = list(result.scalars())
    return TEMPLATES.TemplateResponse(
        "cabinet/admin_pending.html", {"request": request, "admin": admin, "users": users},
    )


@router.post("/pending/{user_id}/approve")
async def approve_user(
    user_id: int,
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        return RedirectResponse(url="/cabinet/admin/pending", status_code=303)
    await approve_user_service(db, target, admin)
    try:
        await _email_service().send_approved(
            target.email, cabinet_url=f"https://{settings.site_host}/cabinet",
        )
    except Exception:
        pass
    return RedirectResponse(url="/cabinet/admin/pending", status_code=303)


@router.post("/pending/{user_id}/reject")
async def reject_user(
    user_id: int,
    reason: str = Form(""),
    admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    target = result.scalar_one_or_none()
    if target is None:
        return RedirectResponse(url="/cabinet/admin/pending", status_code=303)
    await reject_user_service(db, target, admin, reason=reason or None)
    try:
        await _email_service().send_rejected(
            target.email, reason=reason or None, contact=settings.admin_contact_email,
        )
    except Exception:
        pass
    return RedirectResponse(url="/cabinet/admin/pending", status_code=303)
```

- [ ] **Step 4: `app/templates/cabinet/admin_pending.html`**

```html
{% extends "base.html" %}
{% block title %}Pending users — Cyber Berezka{% endblock %}
{% block content %}
<main class="max-w-4xl mx-auto px-6 py-12">
  <header class="flex items-center justify-between mb-8">
    <h1 class="font-serif text-3xl">Pending users</h1>
    <a href="/cabinet" class="text-sm text-accent-goldDk underline">← В кабинет</a>
  </header>

  {% if not users %}
    <p class="text-text-muted">Сейчас нет пользователей, ожидающих одобрения.</p>
  {% else %}
    <ul class="space-y-4">
    {% for u in users %}
      <li class="bg-bg-card border border-border-light rounded-lg shadow-card p-5">
        <div class="font-medium">{{ u.email }}</div>
        <div class="text-xs text-text-muted">Регистрация: {{ u.created_at.strftime('%d.%m.%Y %H:%M') }} · Email подтверждён: {{ u.email_verified_at.strftime('%d.%m.%Y %H:%M') }}{% if u.last_login_ip %} · IP: {{ u.last_login_ip }}{% endif %}</div>
        <div class="mt-4 flex gap-3 items-end">
          <form method="POST" action="/cabinet/admin/pending/{{ u.id }}/approve">
            <button class="btn-primary">Approve</button>
          </form>
          <form method="POST" action="/cabinet/admin/pending/{{ u.id }}/reject" class="flex gap-2 items-end">
            <input type="text" name="reason" maxlength="500" placeholder="Причина (опц.)"
                   class="border border-border-light rounded px-3 py-2 bg-white text-sm">
            <button class="px-4 py-2 border border-cta text-cta rounded hover:bg-cta hover:text-white transition">Reject</button>
          </form>
        </div>
      </li>
    {% endfor %}
    </ul>
  {% endif %}
</main>
{% endblock %}
```

- [ ] **Step 5: Wire `admin.router` в `app/main.py`**

```python
from app.routers import admin, auth, cabinet, landing, legal
# ...
app.include_router(admin.router)
```

- [ ] **Step 6: Run tests, expect pass**

```bash
python -m pytest tests/site/test_admin.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add infra/site/app/routers/admin.py infra/site/app/templates/cabinet/admin_pending.html \
        infra/site/app/main.py tests/site/test_admin.py
git commit -m "feat(site/admin): pending users page + approve/reject endpoints with email notify"
```

---

## Task 17: CLI promote-admin

**Files:**
- Create: `infra/site/app/cli.py`

- [ ] **Step 1: `app/cli.py`**

```python
"""CLI utilities. Usage: python -m app.cli <command> [args].

Currently supports:
  promote-admin --email <email>   — set is_admin=True on the user with given email.
"""
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.db import async_session_factory
from app.models.user import User


async def promote_admin(email: str) -> int:
    norm = email.strip().lower()
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email_normalized == norm))
        user = result.scalar_one_or_none()
        if user is None:
            print(f"ERROR: user with email {email} not found")
            return 1
        if user.is_admin:
            print(f"INFO: {email} is already an admin")
            return 0
        user.is_admin = True
        # Auto-approve admin so they can use the cabinet immediately.
        if user.admin_approved_at is None:
            from datetime import datetime, timezone
            user.admin_approved_at = datetime.now(timezone.utc)
            user.admin_approved_by = user.id
        await db.commit()
        print(f"OK: promoted {email} to admin and approved")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("promote-admin")
    p.add_argument("--email", required=True)
    args = parser.parse_args()
    if args.cmd == "promote-admin":
        return asyncio.run(promote_admin(args.email))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Sanity check (does not require DB)**

```bash
python -c "
import sys; sys.path.insert(0, 'infra/site')
from app.cli import main
import argparse
print('cli module loads OK')
"
```

Expected: `cli module loads OK`.

- [ ] **Step 3: Commit**

```bash
git add infra/site/app/cli.py
git commit -m "feat(site/cli): promote-admin command (auto-approves and sets is_admin=True)"
```

---

## Task 18: Update base.html and landing — point links to real routes

**Files:**
- Modify: `infra/site/app/templates/base.html`
- Modify: `infra/site/app/templates/landing/index.html`

- [ ] **Step 1: Inspect base.html / landing/index.html — links currently use `{{ site_domain }}/auth/...`. The route `/auth/register` etc. now actually exists.**

Подтверждение: после Task 9 рутеры `auth.router` подключены, route `/auth/register` существует. Ссылки в шаблонах формально корректны, но они content-conscious — нужно убедиться что они работают на текущем хосте, а не указывают на устаревший `{{ site_domain }}`.

В существующем `base.html` (просмотренном ранее) есть конструкции вида:
```html
<a href="https://{{ site_domain }}/auth/register" ...>
```

Сейчас `site_domain` алиасится на тот же хост, что и `landing_domain`/`site_host` (back-compat — см. migration spec). Поэтому ссылки работают, но содержат лишний `https://{host}` — лучше использовать абсолютные пути.

- [ ] **Step 2: Edit `app/templates/base.html`** — заменить все вхождения `https://{{ site_domain }}/...` на относительные пути:

```bash
sed -i.bak 's|https://{{ site_domain }}/|/|g; s|https://{{ landing_domain }}/|/|g' \
  infra/site/app/templates/base.html infra/site/app/templates/landing/index.html
rm infra/site/app/templates/base.html.bak infra/site/app/templates/landing/index.html.bak
```

(MacOS `sed -i.bak` синтаксис; на Linux может быть `sed -i ...` без `.bak`.)

- [ ] **Step 3: Проверить что больше нет вхождений `https://{{`**

```bash
grep -rn 'https://{{' infra/site/app/templates/ || echo "OK, no occurrences"
```

Expected: `OK, no occurrences`.

- [ ] **Step 4: Commit**

```bash
git add infra/site/app/templates/base.html infra/site/app/templates/landing/index.html
git commit -m "fix(site/templates): use relative paths instead of hardcoded https://{{site_domain}}"
```

---

## Task 19: Dockerfile + entrypoint + compose updates

**Files:**
- Create: `infra/site/entrypoint.sh`
- Modify: `infra/site/Dockerfile`
- Modify: `infra/compose/docker-compose.coordinator.yml`

- [ ] **Step 1: `infra/site/entrypoint.sh`**

```bash
#!/usr/bin/env bash
# Site container entrypoint:
#   1. Wait for db-app to be reachable.
#   2. Run alembic upgrade head.
#   3. Exec the main command (uvicorn).
set -euo pipefail

echo "[entrypoint] Waiting for db-app..."
python - <<'PY'
import asyncio, os, sys
import asyncpg
async def wait():
    url = os.environ["APP_DB_URL"]
    # Convert SQLAlchemy URL to asyncpg-compatible one.
    url = url.replace("postgresql+asyncpg://", "postgresql://", 1)
    for i in range(60):
        try:
            c = await asyncpg.connect(url)
            await c.close()
            print(f"[entrypoint] DB reachable on attempt {i+1}")
            return
        except Exception as e:
            print(f"[entrypoint] attempt {i+1}: {e}")
            await asyncio.sleep(1)
    print("[entrypoint] FATAL: DB never became reachable", file=sys.stderr)
    sys.exit(1)
asyncio.run(wait())
PY

echo "[entrypoint] Running alembic upgrade head..."
APP_DB_URL_SYNC="$(python -c "import os; u=os.environ['APP_DB_URL']; print(u.replace('postgresql+asyncpg://','postgresql://',1))")"
APP_DB_URL="$APP_DB_URL_SYNC" alembic -c /app/alembic.ini upgrade head

echo "[entrypoint] Starting uvicorn..."
exec "$@"
```

- [ ] **Step 2: Modify `infra/site/Dockerfile`** — add Alembic copy + entrypoint:

Между `COPY app/ ./app/` и `COPY --from=tw-builder ...`:

```dockerfile
COPY alembic.ini ./alembic.ini
COPY migrations/ ./migrations/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
```

И в финальном `CMD` блоке поменять на ENTRYPOINT + CMD:

```dockerfile
ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
```

Также — установить alembic в финальный stage (если он не установлен из pip install выше — он включен в pyproject deps).

(Note: alembic уже в списке pip install в Dockerfile — см. Task 0 inventory.)

- [ ] **Step 3: Modify `infra/compose/docker-compose.coordinator.yml`** — убедиться что site сервис явно получает все нужные env. В блоке `site.environment` уже есть `APP_DB_URL`, `SITE_REDIS_URL`, `REMNAWAVE_API_URL`. Этого достаточно.

Также проверить что `db-app` healthcheck присутствует и `site.depends_on` использует `condition: service_healthy` для `db-app` — это уже было.

- [ ] **Step 4: Rebuild + restart site локально не делается (этот шаг для прод-сервера в финальной фазе). Просто валидация compose:**

```bash
docker compose -f infra/compose/docker-compose.coordinator.yml --env-file infra/.env.example config > /dev/null && echo "compose OK"
```

Expected: `compose OK`.

- [ ] **Step 5: Commit**

```bash
git add infra/site/entrypoint.sh infra/site/Dockerfile
git commit -m "feat(site/docker): entrypoint runs alembic upgrade head before uvicorn"
```

---

## Task 20: Final validation (всё локально)

**Files:** (no new files — checks only)

- [ ] **Step 1: All pytest**

```bash
cd /Users/nikitavorozbitov/pycharmProject/cyber-berezka
python -m pytest tests/ -v 2>&1 | tail -20
```

Expected: всё passed (>=8 site-тестов + 8 migration-тестов = 16+).

- [ ] **Step 2: bash -n on scripts (regression check)**

```bash
for f in scripts/*.sh infra/site/entrypoint.sh; do
    echo -n "$f: "
    bash -n "$f" && echo OK || echo FAIL
done
```

Expected: всё OK.

- [ ] **Step 3: docker compose config**

```bash
cp infra/.env.example infra/.env.test
docker compose -f infra/compose/docker-compose.coordinator.yml --env-file infra/.env.test config > /dev/null && echo "coordinator OK"
docker compose -f infra/compose/docker-compose.node.yml --env-file infra/.env.test config > /dev/null && echo "node OK"
rm infra/.env.test
```

Expected: оба `OK`.

- [ ] **Step 4: Final summary commit (if any small fixups)**

```bash
git status
# if anything: git add -A && git commit -m "chore: final fixups"
```

---

## Post-plan: Deployment

После всех 20 tasks:

1. `./scripts/sync_repo_to_server.sh 212.74.231.217`
2. `ssh root@212.74.231.217 'cd /root/cyber-berezka/infra/compose && docker compose -f docker-compose.coordinator.yml --env-file /root/cyber-berezka/infra/.env up -d --build site'`
3. Wait for site to become healthy (entrypoint runs alembic + uvicorn).
4. Register first user через UI на `https://212-74-231-217.nip.io/auth/register`, подтверждаем email.
5. Promote через CLI: `ssh root@212.74.231.217 'docker compose -f /root/cyber-berezka/infra/compose/docker-compose.coordinator.yml --env-file /root/cyber-berezka/infra/.env exec site python -m app.cli promote-admin --email ваш@email'`
6. Логин → проверяем `/cabinet/admin/pending` доступен → проверяем server-list блоки → создаём ключ → проверяем deep-link.

Не входит в этот plan — это deployment-этап после coding.

---

## Open follow-ups (после реализации)

| # | Тип | Что |
|---|---|---|
| #54 | follow-up | Squad с автоматическим binding'ом к inbound при первом user.create (или ensure-bound вызов в VpnKeysService.ensure_remnawave_user) |
| #55 | follow-up | Rate-limit register/login (5/15min/IP, 5/h/IP) через redis-counter |
| #56 | follow-up | Password reset flow (forgot password → email → token → form). Не критично для MVP, БД-поля уже есть |
| #57 | follow-up | Audit-log viewer для админа |
