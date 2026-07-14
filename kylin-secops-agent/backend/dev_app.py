"""
Development entry point for uvicorn.
Applies PostgreSQL→SQLite patches BEFORE importing the real app module.
Usage: uvicorn dev_app:app --reload --port 8000
"""

import os
import sys

# ── Apply env overrides FIRST ──
os.environ.setdefault("JWT_ALGORITHM", "HS256")
# JWT_SECRET_KEY must come from the environment (or a per-install secret.key).
# If unset, generate an ephemeral in-memory key for this dev session — never
# hardcode a shared secret that could forge tokens across installs.
import secrets as _secrets
if not os.environ.get("JWT_SECRET_KEY"):
    os.environ["JWT_SECRET_KEY"] = _secrets.token_hex(48)
os.environ.setdefault("REDIS_HOST", "")
# dev_app is for local development only; DEBUG stays off unless explicitly set.
os.environ.setdefault("DEBUG", os.environ.get("KYLIN_DEBUG", "False"))
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./kylin_secops_dev.db"

# ── Patch PostgreSQL types to SQLite-compatible equivalents ──
import sqlalchemy.types as sa_types
from sqlalchemy.dialects import postgresql as pg_dialect

class _UUIDType(sa_types.String):
    """Callable replacement for postgresql.UUID (supports UUID(as_uuid=True))."""
    def __init__(self, as_uuid=True):
        super().__init__(36)

pg_dialect.INET = sa_types.String
pg_dialect.UUID = _UUIDType
pg_dialect.JSONB = sa_types.JSON
pg_dialect.ARRAY = sa_types.JSON
pg_dialect.TSVECTOR = sa_types.String

# ── Patch create_async_engine to strip asyncpg-specific kwargs ──
from sqlalchemy.ext.asyncio import create_async_engine as _orig_ce
def _patched_ce(url, **kw):
    if isinstance(url, str) and url.startswith("sqlite"):
        ca = kw.pop("connect_args", {})
        clean = {k: v for k, v in ca.items()
                 if k not in ("statement_cache_size", "prepared_statement_cache_size")}
        if clean:
            kw["connect_args"] = clean
        kw["poolclass"] = None  # Use default pool for SQLite
    return _orig_ce(url, **kw)

import sqlalchemy.ext.asyncio as sa_async
sa_async.create_async_engine = _patched_ce

# ── Override settings.DATABASE_URL ──
import app.core.config as cfg

class _SQLiteURL:
    def __get__(self, obj, objtype=None):
        return "sqlite+aiosqlite:///./kylin_secops_dev.db"
    def __set__(self, obj, val):
        pass

cfg.Settings.DATABASE_URL = _SQLiteURL()

# ── Register SQLite gen_random_uuid() event ──
from sqlalchemy import event as sa_event
from app.core.database import engine

@sa_event.listens_for(engine.sync_engine, "connect")
def _sqlite_setup(dbapi_conn, _record):
    import sqlite3
    if not isinstance(dbapi_conn, sqlite3.Connection):
        return
    import uuid
    dbapi_conn.create_function("gen_random_uuid", 0, lambda: str(uuid.uuid4()))

# ── Import the real app ──
from app.main import app

print("[dev_app] Patches applied, app loaded successfully")
