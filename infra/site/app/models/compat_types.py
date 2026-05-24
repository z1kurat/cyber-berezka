"""SQLAlchemy TypeDecorators for PostgreSQL-specific types.

These decorators transparently use native PostgreSQL types on PostgreSQL
and fall back to TEXT/String/Integer on other backends (e.g., SQLite for tests).
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.dialects.postgresql import INET as PG_INET
from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator


class BigInt(TypeDecorator):
    """BigInteger on PostgreSQL, Integer on everything else (SQLite autoincrement)."""

    impl = Integer
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(BigInteger())
        return dialect.type_descriptor(Integer())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value


class INET(TypeDecorator):
    """INET on PostgreSQL, TEXT on everything else."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_INET())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        return value

    def process_result_value(self, value, dialect):
        return value


class UUID(TypeDecorator):
    """UUID (as string) on PostgreSQL, String(36) on everything else."""

    impl = String
    cache_ok = True

    def __init__(self, as_uuid: bool = True, **kwargs):
        self.as_uuid = as_uuid
        super().__init__(36, **kwargs)

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=self.as_uuid))
        return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        return value


class JSONB(TypeDecorator):
    """JSONB on PostgreSQL, TEXT (JSON-encoded) on everything else."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_JSONB())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: Any, dialect: Dialect):
        if dialect.name != "postgresql" and value is not None:
            return json.dumps(value)
        return value

    def process_result_value(self, value: Any, dialect: Dialect):
        if dialect.name != "postgresql" and isinstance(value, str):
            return json.loads(value)
        return value
