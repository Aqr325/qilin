"""
麒麟OS安全智能运维Agent — 桌面版后端入口
打包成 backend.exe（windowed mode，无控制台窗口）
运行时读取同目录下的 config.json
"""
import json
import os
import sys

# ══════════════════════════════════════════════════════════════
# 1. Load config.json from EXE's parent directory
# ══════════════════════════════════════════════════
if getattr(sys, 'frozen', False):
    EXE_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    EXE_DIR = os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(EXE_DIR, 'config.json')
config = {}
if os.path.isfile(CONFIG_PATH):
    try:
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        print(f"[WARN] config.json 解析失败: {e}，使用默认配置")

# Extract backend config with defaults
be = config.get('backend', {})
db = be.get('database', {})
jwt = be.get('jwt', {})
redis_cfg = be.get('redis', {})
desktop = config.get('desktop', {})

DB_URL = db.get('url', 'kylin_secops.db')
BACKEND_HOST = be.get('host', '127.0.0.1')
BACKEND_PORT = be.get('port', 8000)
JWT_ALGO = jwt.get('algorithm', 'HS256')
JWT_KEY = jwt.get('secret_key', '')
if not JWT_KEY:
    import secrets
    JWT_KEY = secrets.token_hex(32)
    print("[WARN] JWT secret_key not configured, using random temporary key")
REDIS_ENABLED = redis_cfg.get('enabled', False)
REDIS_HOST = redis_cfg.get('host', '') if REDIS_ENABLED else ''
DEBUG = be.get('debug', False)
# Top-level seed_password → KYLIN_SEED_PASSWORD (used by DB seed for default accounts)
SEED_PASSWORD = config.get('seed_password', '')

# Ensure data/ directory exists
data_dir = os.path.join(EXE_DIR, desktop.get('data_directory', './data'))
os.makedirs(data_dir, exist_ok=True)

# Normalize DB_URL to a valid SQLAlchemy URL
if DB_URL == 'InMemoryDB' or DB_URL == '':
    # Desktop default: kylin_secops.db in EXE_DIR
    abs_db = os.path.join(EXE_DIR, 'kylin_secops.db')
    DB_URL = f"sqlite+aiosqlite:///{abs_db}"
elif DB_URL.startswith(('sqlite', 'postgresql', 'mysql', 'oracle', 'mssql')):
    # Already a proper SQLAlchemy URL
    if DB_URL.startswith('sqlite') and './' in DB_URL:
        db_filename = DB_URL.split('/')[-1]
        abs_db = os.path.join(EXE_DIR, db_filename)
        DB_URL = f"sqlite+aiosqlite:///{abs_db}"
else:
    # Plain filename → treat as relative SQLite path under EXE_DIR
    abs_db = os.path.join(EXE_DIR, DB_URL)
    DB_URL = f"sqlite+aiosqlite:///{abs_db}"

# ══════════════════════════════════════════════════════════════
# 2. Env overrides — config.json values as fallback (respect env vars)
# ══════════════════════════════════════════════
os.environ.setdefault("JWT_ALGORITHM", JWT_ALGO)
os.environ.setdefault("JWT_SECRET_KEY", JWT_KEY)
os.environ.setdefault("REDIS_HOST", REDIS_HOST)
os.environ.setdefault("DEBUG", str(DEBUG))
os.environ.setdefault("EXE_DIR", EXE_DIR)
os.environ.setdefault("KYLIN_SEED_PASSWORD", SEED_PASSWORD)
os.environ.setdefault("DATABASE_URL", DB_URL)  # respect env var DATABASE_URL

# ══════════════════════════════════════════════════════════════
# 3. PostgreSQL → SQLite patches (must run before app imports)
# ══════════════════════════════════════════════════
import sqlalchemy.types as sa_types
from sqlalchemy.dialects import postgresql as pg_dialect


class _UUIDType(sa_types.String):
    def __init__(self, as_uuid=True):
        super().__init__(36)


pg_dialect.INET = sa_types.String
pg_dialect.UUID = _UUIDType
pg_dialect.JSONB = sa_types.JSON
pg_dialect.ARRAY = sa_types.JSON
pg_dialect.TSVECTOR = sa_types.String

# Patch create_async_engine to strip asyncpg-specific kwargs
from sqlalchemy.ext.asyncio import create_async_engine as _orig_ce


def _patched_ce(url, **kw):
    if isinstance(url, str) and url.startswith("sqlite"):
        ca = kw.pop("connect_args", {})
        clean = {k: v for k, v in ca.items()
                 if k not in ("statement_cache_size", "prepared_statement_cache_size")}
        if clean:
            kw["connect_args"] = clean
        kw["poolclass"] = None
    return _orig_ce(url, **kw)


import sqlalchemy.ext.asyncio as sa_async
sa_async.create_async_engine = _patched_ce

# Override settings.DATABASE_URL descriptor
import app.core.config as cfg


class _SQLiteURL:
    def __get__(self, obj, objtype=None):
        return DB_URL

    def __set__(self, obj, val):
        pass


cfg.Settings.DATABASE_URL = _SQLiteURL()


# ══════════════════════════════════════════════════════════════
# 4. Start API server
# ══════════════════════════════════════════════
from app.main import app
import asyncio


if __name__ == "__main__":
    import uvicorn
    # Use blocking run so the EXE stays alive
    uvicorn.run(
        app,
        host=BACKEND_HOST,
        port=BACKEND_PORT,
        log_level=be.get('log_level', 'info'),
        access_log=False,
        use_colors=False,
    )