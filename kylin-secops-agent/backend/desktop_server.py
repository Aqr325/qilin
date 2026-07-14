"""
麒麟OS 安全智能运维Agent — 桌面版入口
持久化 SQLite 数据库 + 种子数据自动初始化
"""

import os
import sys
import uuid

# SQL import used later for sqlite3 in event registration
import sqlite3

# hashlib used for backward-compatible password hashing in legacy code
import hashlib

# random/timedelta used in seed helper functions
from datetime import datetime, timedelta


# ══════════════════════════════════════════════════════════════
# Determine base directory (PyInstaller _MEIPASS or dev)
# ══════════════════════════════════════════════════════════════
def _get_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


BASE_DIR = _get_base_dir()

# Data directory (writable, next to the exe or in cwd)
def _get_data_dir() -> str:
    if getattr(sys, "frozen", False):
        # Desktop app: data file placed next to executable
        return os.path.dirname(os.path.abspath(sys.executable))
    return BASE_DIR


DATA_DIR = _get_data_dir()
DB_PATH = os.path.join(DATA_DIR, "kylin_secops.db")


# ══════════════════════════════════════════════════════════════
# Apply PostgreSQL → SQLite patches (MUST run before app imports)
# ══════════════════════════════════════════════════════════════

os.environ["JWT_ALGORITHM"] = "HS256"

# ── Per-install JWT secret (NO hardcoded key) ──
# Priority: env JWT_SECRET_KEY > <DATA_DIR>/secret.key > generate + persist (0600).
# Mirrors backend_entry.py so every desktop install signs tokens with its own key.
_SECRET_FILE = os.path.join(DATA_DIR, "secret.key")
_env_jwt = os.environ.get("JWT_SECRET_KEY")
if _env_jwt:
    _JWT_KEY = _env_jwt
elif os.path.isfile(_SECRET_FILE):
    try:
        with open(_SECRET_FILE, "r", encoding="utf-8") as _sf:
            _JWT_KEY = _sf.read().strip()
    except OSError:
        _JWT_KEY = ""
else:
    _JWT_KEY = ""
if not _JWT_KEY:
    import secrets as _secrets
    _JWT_KEY = _secrets.token_hex(48)
    try:
        with open(_SECRET_FILE, "w", encoding="utf-8") as _sf:
            _sf.write(_JWT_KEY)
        try:
            os.chmod(_SECRET_FILE, 0o600)
        except OSError:
            pass
    except OSError:
        pass
os.environ["JWT_SECRET_KEY"] = _JWT_KEY

os.environ["REDIS_HOST"] = ""
# DEBUG is NEVER forced on. Enable only via explicit env KYLIN_DEBUG=True.
os.environ["DEBUG"] = os.environ.get("KYLIN_DEBUG", "False")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{DB_PATH}"

import sqlalchemy.types as sa_types
from sqlalchemy.dialects import postgresql as pg_dialect


class _UUIDType(sa_types.String):
    """Callable replacement for postgresql.UUID (supports UUID(as_uuid=True))."""
    def __init__(self, as_uuid: bool = True):
        super().__init__(36)


pg_dialect.INET = sa_types.String
pg_dialect.UUID = _UUIDType
pg_dialect.JSONB = sa_types.JSON
pg_dialect.ARRAY = sa_types.JSON
pg_dialect.TSVECTOR = sa_types.String

from sqlalchemy.ext.asyncio import create_async_engine as _orig_ce


def _patched_ce(url, **kw):
    if isinstance(url, str) and url.startswith("sqlite"):
        ca = kw.pop("connect_args", {})
        clean = {k: v for k, v in ca.items()
                 if k not in ("statement_cache_size", "prepared_statement_cache_size")}
        if clean:
            kw["connect_args"] = clean
    return _orig_ce(url, **kw)


import sqlalchemy.ext.asyncio as sa_async
sa_async.create_async_engine = _patched_ce

import app.core.config as cfg


class _SQLiteURL:
    def __get__(self, obj, objtype=None):
        return f"sqlite+aiosqlite:///{DB_PATH}"
    def __set__(self, obj, val):
        pass


cfg.Settings.DATABASE_URL = _SQLiteURL()
from app.core.config import settings


# ══════════════════════════════════════════════════════════════
# Database initialization and seeding (unified with ORM)
# ══════════════════════════════════════════════════════════════

# Disable auto-seeding in init_db() when running from desktop_server
# We control seeding ourselves to avoid race conditions.
_SEED_LOCK = object()


async def _ensure_db_ready():
    """Ensure DB tables exist + seed data. Idempotent and safe to call multiple times."""
    from sqlalchemy import select, func
    import asyncio

    # 1. Create all tables via ORM (handles schema consistency)
    from app.core.database import engine, async_session_factory, Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Check if we need to seed default users (only on fresh DB)
    from app.models.user import User
    async with async_session_factory() as session:
        result = await session.execute(func.count(User.id))
        user_count = result.scalar_one()
        if user_count > 0:
            print(f"[Desktop] DB already has {user_count} user(s), skipping seed")
            return

    # 3. Seed default users + roles + permissions via ORM
    await _seed_defaults()


async def _seed_defaults():
    """Seed default roles, permissions, and users using the ORM."""
    from sqlalchemy import select, func
    import uuid as _uuid
    from datetime import datetime, timezone

    from app.core.permissions import Permission as PermissionEnum, DEFAULT_SEED_USERS, ROLE_PERMISSIONS, _resolve_seed_password
    from app.core.security import hash_password
    from app.models.user import User, Role, Permission as PermissionModel
    from app.core.database import async_session_factory

    _all_perms = sorted([p.value for p in PermissionEnum])
    display_names = {
        "admin": "管理员", "operator": "操作员",
        "auditor": "审计员", "readonly": "只读用户"
    }

    async with async_session_factory() as session:
        # — Permissions —
        perm_map = {}
        for code in _all_perms:
            session.add(PermissionModel(
                id=_uuid.uuid4(), code=code,
                name=code.split(":", 1)[1].replace("_", " ").title() if ":" in code else code,
                module=code.split(":")[0] if ":" in code else "system",
                action=code.split(":", 1)[1] if ":" in code else code,
            ))
        await session.flush()

        result = await session.execute(select(PermissionModel))
        perm_map = {p.code: p for p in result.scalars()}

        # — Roles —
        role_map = {}
        for role_name in ROLE_PERMISSIONS:
            session.add(Role(
                id=_uuid.uuid4(), name=role_name,
                display_name=display_names.get(role_name, role_name),
                is_system=True,
            ))
        await session.flush()

        result = await session.execute(select(Role))
        role_map = {r.name: r for r in result.scalars()}

        # — Assign permissions to roles —
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role = role_map.get(role_name)
            if not role:
                continue
            role.permissions = [perm_map[c] for c in perm_codes if c in perm_map]

        # — Default users —
        for su in DEFAULT_SEED_USERS:
            role = role_map.get(su["role"])
            if not role:
                continue
            session.add(User(
                id=_uuid.uuid4(), username=su["username"],
                password_hash=hash_password(_resolve_seed_password(su["username"])),
                display_name=su["display_name"],
                email=su["email"],
                is_active=True,
                password_changed_at=datetime.now(timezone.utc),
            ))
            u = session.new  # placeholder — flush first to get ID
        await session.flush()

        # Link users to roles
        for su in DEFAULT_SEED_USERS:
            user_obj = await session.execute(
                select(User).where(User.username == su["username"])
            )
            u = user_obj.scalar_one()
            role = role_map.get(su["role"])
            if role and role not in u.roles:
                u.roles.append(role)

        await session.commit()
        print("[Desktop] Default roles, permissions, and users seeded.")


def _seed_database_sync():
    """Sync wrapper for _ensure_db_ready() — called from main thread."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_ensure_db_ready())
    except Exception as e:
        print(f"[Desktop] Warning: DB seed failed ({e}). Will retry on app startup.")


# ══════════════════════════════════════════════════════════════
# Register SQLite gen_random_uuid() event
# ══════════════════════════════════════════════════════════════
# (No longer needed — models use default=uuid.uuid4 instead of server_default=func.gen_random_uuid())


# ══════════════════════════════════════════════════════════════
# Main entry
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=" * 60)
    print("  麒麟OS 安全智能运维Agent - 桌面版")
    print("=" * 60)
    print(f"  [DB] {DB_PATH}")
    print(f"  [JWT] HS256 (本地模式)")
    print(f"  [Redis] 已跳过")

    # Auto-seed on first run
    _seed_database_sync()

    # Import the FastAPI app
    from app.main import app

    # Start uvicorn
    import uvicorn
    print()
    print(f"  [API] http://localhost:8001")
    print(f"  [Docs] http://localhost:8001/docs")
    print(f"  [Login] admin / (auto-generated or KYLIN_SEED_PASSWORD env var)")
    print()

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8001,
        reload=False,
        log_level="info",
    )
