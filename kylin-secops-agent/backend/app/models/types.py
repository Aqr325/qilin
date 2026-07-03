"""
SQLite-compatible type aliases for local development.
In production (PostgreSQL), these are handled by patches in dev_app.py
or by using proper PostgreSQL dialect.
"""
import uuid
from sqlalchemy import BigInteger, String, JSON, Integer, types


class _UUIDType(types.TypeDecorator):
    """SQLite-compatible UUID type — stores as 36-char string."""
    impl = String(36)
    cache_ok = True

    def __init__(self, as_uuid=True):
        super().__init__()
        self._as_uuid = as_uuid

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return str(value)
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None or not self._as_uuid:
            return value
        if isinstance(value, uuid.UUID):
            return value
        return uuid.UUID(value)


UUID = _UUIDType
INET = String
JSONB = JSON
ARRAY = JSON
TSVECTOR = String
BIGINT = BigInteger