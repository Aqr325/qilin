"""
麒麟OS安全智能运维Agent — 本地开发运行器
使用 SQLite 替代 PostgreSQL，HS256 替代 RS256，跳过 Redis（本地开发用）
"""

import os
import sys
import subprocess

# ══════════════════════════════════════════════════════════════
# Module-level patches — MUST run before any app imports
# These affect ALL processes (main + reload children)
# ══════════════════════════════════════════════════════════════

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

# Patch create_async_engine to strip asyncpg-specific connect_args for SQLite
from sqlalchemy.ext.asyncio import create_async_engine as _orig_create_engine
def _patched_create_engine(url, **kwargs):
    if isinstance(url, str) and url.startswith("sqlite"):
        connect_args = kwargs.pop("connect_args", {})
        clean = {k: v for k, v in connect_args.items()
                 if k not in ("statement_cache_size", "prepared_statement_cache_size")}
        if clean:
            kwargs["connect_args"] = clean
    return _orig_create_engine(url, **kwargs)

import sqlalchemy.ext.asyncio as sa_asyncio
sa_asyncio.create_async_engine = _patched_create_engine

# Override settings BEFORE app imports
os.environ["JWT_ALGORITHM"] = "HS256"
import secrets
os.environ["JWT_SECRET_KEY"] = secrets.token_hex(32)
os.environ["REDIS_HOST"] = ""
os.environ["DEBUG"] = "True"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import app.core.config as cfg

class _SQLiteURL:
    """Descriptor that always returns the SQLite URL."""
    def __get__(self, obj, objtype=None):
        return "sqlite+aiosqlite:///./kylin_secops_dev.db"
    def __set__(self, obj, val):
        pass

cfg.Settings.DATABASE_URL = _SQLiteURL()
from app.core.config import settings

# ══════════════════════════════════════════════════════════════
# Main entry — runs only in the FIRST (main) process
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("[麒麟OS] 安全智能运维Agent - 本地开发模式")
    print(f"[DB] {settings.DATABASE_URL}")
    print(f"[JWT] {settings.JWT_ALGORITHM}")
    print(f"[Redis] 已跳过（本地开发）")
    print()

    # Register SQLite-compatible functions
    from sqlalchemy import event as sa_event
    from app.core.database import engine

    @sa_event.listens_for(engine.sync_engine, "connect")
    def _sqlite_setup(dbapi_connection, connection_record):
        import sqlite3
        if not isinstance(dbapi_connection, sqlite3.Connection):
            return
        import uuid
        def _gen_uuid():
            return str(uuid.uuid4())
        dbapi_connection.create_function("gen_random_uuid", 0, _gen_uuid)

    # Start API server using dev_app (patched for SQLite)
    import uvicorn
    print()
    print("  [Start] API: http://localhost:8000")
    print("  [Start] Docs: http://localhost:8000/docs")
    print()
    print("  [Login] admin / (auto-generated or KYLIN_SEED_PASSWORD env var)")
    print()

    uvicorn.run(
        "dev_app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )