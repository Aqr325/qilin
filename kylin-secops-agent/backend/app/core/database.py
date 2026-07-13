"""Database engine and session management."""

import asyncio
import logging
import random
import uuid
from typing import AsyncGenerator, Optional

from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from sqlalchemy import event

from app.core.config import settings

logger = logging.getLogger(__name__)


# ── Async Engine ──
def _create_engine():
    """Create async engine with SQLite-compatible settings.

    Reads DATABASE_URL from environment first (set by backend_entry.py/desktop_server.py),
    then falls back to config default.
    """
    import os
    url = os.environ.get("DATABASE_URL", settings.DATABASE_URL)
    if url.startswith("sqlite"):
        return create_async_engine(
            url,
            echo=settings.DB_ECHO,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
    else:
        return create_async_engine(
            url,
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            echo=settings.DB_ECHO,
            pool_pre_ping=True,
            connect_args={
                "statement_cache_size": 0,
                "prepared_statement_cache_size": 0,
            },
        )


engine = _create_engine()


# ── SQLite Pragmas: FK enforcement, WAL concurrency, busy timeout ──
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, conn_record):
    """Per-connection pragmas (SQLite only).

    - foreign_keys=ON  -> ON DELETE CASCADE actually fires
    - journal_mode=WAL -> concurrent readers/writers instead of whole-DB write lock
    - busy_timeout     -> avoid 'database is locked' under concurrent heartbeats
    """
    cur = dbapi_conn.cursor()
    try:
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=15000")
    finally:
        cur.close()


# ── Session Factory ──
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


# ── Declarative Base ──
class Base(DeclarativeBase):
    """Base class for all ORM models."""


# ── SQLite lock-aware commit (transient SQLITE_BUSY retry) ──
def _sqlite_errorcode(exc: BaseException) -> Optional[int]:
    """Best-effort extraction of the underlying SQLite error code."""
    code = getattr(exc, "sqlite_errorcode", None)
    if code is None:
        orig = getattr(exc, "orig", None)
        code = getattr(orig, "sqlite_errorcode", None)
    return code


def _is_sqlite_busy(exc: BaseException) -> bool:
    """Precisely detect transient SQLite lock contention (SQLITE_BUSY = 5).

    ONLY matches 'database is locked' / 'database table is locked' (and error
    code 5). Other OperationalErrors (constraint violations, type mismatches)
    are intentionally NOT matched so they surface unchanged — we never swallow
    real errors.
    """
    if not isinstance(exc, OperationalError):
        return False
    msg = str(exc).lower()
    if "database is locked" in msg:
        return True
    return _sqlite_errorcode(exc) == 5


async def commit_with_retry(session: AsyncSession, *, max_retries: int = 5) -> None:
    """Commit, retrying ONLY on transient SQLite lock contention.

    Bounded exponential backoff with full jitter (20ms → 320ms over 5 attempts).
    Any non-lock error (e.g. IntegrityError, type errors) is re-raised
    immediately. Safe to wrap every idempotent write path: a failed commit
    leaves the transaction un-applied, so re-committing re-applies the same
    pending changes (atomic, no double-write).
    """
    attempt = 0
    while True:
        try:
            await session.commit()
            return
        except Exception as exc:  # noqa: BLE001 - narrowed by _is_sqlite_busy
            if attempt >= max_retries or not _is_sqlite_busy(exc):
                raise
            attempt += 1
            backoff = min(0.5, 0.02 * (2 ** (attempt - 1)))
            await asyncio.sleep(backoff * (0.5 + random.random()))


# ── Dependency ──
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await commit_with_retry(session)
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ── Session Context Manager ──
class DatabaseSession:
    """Context manager for database sessions (use outside FastAPI routes)."""

    def __init__(self):
        self.session: Optional[AsyncSession] = None

    async def __aenter__(self) -> AsyncSession:
        self.session = async_session_factory()
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if not self.session:
            return
        try:
            if exc_type is None:
                await commit_with_retry(self.session)
            else:
                await self.session.rollback()
        except Exception:
            await self.session.rollback()
            raise
        finally:
            await self.session.close()


# ── Indexes ──

async def _ensure_indexes():
    """Create additional indexes that are not part of ORM model definitions.

    These indexes target high-frequency query patterns for better performance.
    Tuple shape: (table, columns, index_name, where_clause, unique)
    """
    from sqlalchemy import text as sa_text

    indexes = [
        # ── users ──
        ("user_roles", "user_id, role_id", "ix_user_roles_user_id_role_id", None, False),
        # ── agents ──
        ("agents", "status", "ix_agents_status", None, False),
        # ── alerts ──
        ("alerts", "severity, status", "ix_alerts_severity_status", None, False),
        ("alerts", "status", "ix_alerts_status", None, False),
        ("alerts", "created_at", "ix_alerts_created_at", None, False),
        ("alerts", "alert_seq", "ix_alerts_alert_seq", None, True),
        # ── agent_heartbeats (used as agent_events surrogate) ──
        ("agent_heartbeats", "agent_id, received_at", "ix_agent_heartbeats_agent_time", None, False),
        ("agent_heartbeats", "received_at", "ix_agent_heartbeats_received_at", None, False),
        # ── audit_logs ──
        ("audit_logs", "action, resource_type, created_at", "ix_audit_logs_action_resource_time", None, False),
        ("audit_logs", "user_id, created_at", "ix_audit_logs_user_id_created_at", None, False),
        ("audit_logs", "resource_id", "ix_audit_logs_resource_id", None, False),
        # ── login_logs ──
        ("login_logs", "username, login_at", "ix_login_logs_username_login_at", None, False),
        ("login_logs", "ip_address, login_at", "ix_login_logs_ip_login_at", None, False),
        ("login_logs", "login_at", "ix_login_logs_login_at", None, False),
        # ── policies ──
        ("policies", "policy_type, status", "ix_policies_type_status", None, False),
        ("policies", "status", "ix_policies_status", None, False),
        # ── policy_targets ──
        ("policy_targets", "policy_id, agent_id", "ix_policy_targets_policy_agent", None, False),
        ("policy_targets", "agent_id, status", "ix_policy_targets_agent_status", None, False),
        # ── policy_versions ──
        ("policy_versions", "policy_id", "ix_policy_versions_policy_id", None, False),
        # ── alert_status_history ──
        ("alert_status_history", "alert_id, created_at", "ix_alert_status_history_alert_time", None, False),
        ("alert_status_history", "operator_id", "ix_alert_status_history_operator_id", None, False),
    ]

    async with engine.begin() as conn:
        for table, cols, name, where, unique in indexes:
            kw = "UNIQUE INDEX" if unique else "INDEX"
            sql = f"CREATE {kw} IF NOT EXISTS {name} ON {table} ({cols})"
            if where:
                sql += f" WHERE {where}"
            try:
                await conn.execute(sa_text(sql))
            except Exception as e:
                logger.warning("创建索引 %s 失败（可忽略）: %s", name, e)


async def _migrate_bigint_pk():
    """SQLite-only schema fix.

    Tables created (pre v2.3.3) with a BigInteger primary key cannot auto-assign
    a rowid on INSERT (SQLite only honours INTEGER PRIMARY KEY as the rowid alias),
    so every write to agent_heartbeats / alert_status_history / policy_targets /
    system_settings failed with NOT NULL. Rebuild any such table with an INTEGER
    PK (auto-increment rowid alias), preserving existing rows.

    Implementation note: we reuse the table's own CREATE TABLE statement (read from
    sqlite_master) and replace the single BIGINT PK column with INTEGER, rather than
    asking SQLAlchemy to re-emit DDL (its custom INET/JSONB types don't compile
    cleanly for SQLite DDL generation). The rest of the schema is preserved verbatim.
    """
    targets = ["agent_heartbeats", "alert_status_history", "policy_targets", "system_settings"]
    from sqlalchemy import text

    async with engine.begin() as conn:
        for name in targets:
            res = await conn.execute(
                text("SELECT sql FROM sqlite_master WHERE type='table' AND name=:n"),
                {"n": name},
            )
            row = res.fetchone()
            if not row or not row[0] or "BIGINT" not in row[0].upper():
                continue  # no table, or already INTEGER PK -> nothing to do
            # Exactly one BIGINT column exists per target table (the id PK).
            new_sql = row[0].replace("BIGINT", "INTEGER").replace("bigint", "INTEGER")
            old = f"{name}__mig_old"
            try:
                await conn.execute(text(f'ALTER TABLE "{name}" RENAME TO "{old}"'))
                await conn.execute(text(new_sql))
                cols_res = await conn.execute(text(f"PRAGMA table_info('{old}')"))
                csv = ", ".join(f'"{c[1]}"' for c in cols_res.fetchall())
                try:
                    await conn.execute(text(f'INSERT INTO "{name}" ({csv}) SELECT {csv} FROM "{old}"'))
                    await conn.execute(text(f'DROP TABLE "{old}"'))
                    logger.info("迁移 BIGINT PK -> INTEGER PK: %s", name)
                except Exception as copy_err:
                    await conn.execute(text(f'DROP TABLE IF EXISTS "{name}"'))
                    await conn.execute(text(f'ALTER TABLE "{old}" RENAME TO "{name}"'))
                    logger.warning("迁移 %s 数据复制失败，已回退: %s", name, copy_err)
            except Exception as e:
                logger.warning("迁移 %s 结构变更失败（保留原表）: %s", name, e)


async def init_db():
    """Create all tables, migrate schema, build indexes, seed defaults."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # ── Migrate legacy BIGINT PK tables (SQLite auto-increment fix) ──
    await _migrate_bigint_pk()

    # ── Create indexes ──
    await _ensure_indexes()

    # Seed roles, permissions, and default users on first run
    from datetime import datetime, timezone
    import uuid as _uuid

    from sqlalchemy import select, func

    # Import the Permission ENUM (not the SQLAlchemy model)
    from app.core.permissions import (
        Permission as PermissionEnum,
        DEFAULT_SEED_USERS,
        ROLE_PERMISSIONS,
        _resolve_seed_password,
    )
    from app.core.security import hash_password
    from app.models.user import User, Role, Permission as PermissionModel

    # Build a sorted list of all permission codes from the Enum
    _all_perms = sorted([p.value for p in PermissionEnum])

    async with async_session_factory() as session:
        # 1. Seed permissions
        existing_perm_codes = set()
        result = await session.execute(select(PermissionModel.code))
        for row in result.scalars():
            existing_perm_codes.add(row)

        for code in _all_perms:
            if code not in existing_perm_codes:
                parts = code.split(":", 1)
                session.add(PermissionModel(
                    id=_uuid.uuid4(),
                    code=code,
                    name=parts[1].replace("_", " ").title(),
                    module=parts[0],
                    action=parts[1],
                ))
        await session.flush()

        # Reload permissions
        result = await session.execute(select(PermissionModel))
        perm_map = {p.code: p for p in result.scalars()}

        # 2. Seed roles
        existing_role_names = set()
        result = await session.execute(select(Role.name))
        for row in result.scalars():
            existing_role_names.add(row)

        display_names = {
            "admin": "管理员", "operator": "操作员",
            "auditor": "审计员", "readonly": "只读用户"
        }
        for role_name in ROLE_PERMISSIONS:
            if role_name not in existing_role_names:
                session.add(Role(
                    id=_uuid.uuid4(),
                    name=role_name,
                    display_name=display_names.get(role_name, role_name),
                    is_system=True,
                ))
        await session.flush()

        # Reload roles
        result = await session.execute(select(Role))
        role_map = {r.name: r for r in result.scalars()}

        # 3. Assign permissions to roles via raw SQL (avoid lazy-load greenlet issue)
        from sqlalchemy import text as sa_text
        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role = role_map.get(role_name)
            if not role:
                continue
            for code in perm_codes:
                if code in perm_map:
                    await session.execute(
                        sa_text("""
                            INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                            VALUES (:role_id, :permission_id)
                        """), {
                            "role_id": str(role.id),
                            "permission_id": str(perm_map[code].id),
                        }
                    )

        # 4. Seed default users
        result = await session.execute(select(func.count(User.id)))
        user_count = result.scalar_one()
        if user_count == 0:
            for su in DEFAULT_SEED_USERS:
                role = role_map.get(su["role"])
                session.add(User(
                    id=_uuid.uuid4(),
                    username=su["username"],
                    password_hash=hash_password(_resolve_seed_password(su["username"])),
                    display_name=su["display_name"],
                    email=su["email"],
                    is_active=True,
                    password_changed_at=datetime.now(timezone.utc),
                ))
                # Roles are linked via backref after flush
            await session.flush()

        # Link users to roles (direct raw SQL to avoid UUID serialization in ORM)
        from sqlalchemy import text as sa_text
        for su in DEFAULT_SEED_USERS:
            user_obj = await session.execute(
                select(User).where(User.username == su["username"])
            )
            u = user_obj.scalar_one()
            role = role_map.get(su["role"])
            if role:
                await session.execute(
                    sa_text("""
                        INSERT OR IGNORE INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                    """), {
                        "user_id": str(u.id),
                        "role_id": str(role.id),
                    }
                )

        # 5. Seed default model configs for each user (if none exist)
        from app.models.ai import AiModelConfig
        from sqlalchemy import select, func as sql_func

        # Only seed for the admin user as a default template
        admin_user = await session.execute(
            select(User).where(User.username == "admin")
        )
        admin = admin_user.scalar_one_or_none()
        if admin:
            existing_configs = await session.execute(
                select(sql_func.count(AiModelConfig.id)).where(AiModelConfig.user_id == admin.id)
            )
            config_count = existing_configs.scalar_one() or 0
            if config_count == 0:
                # Seed a default mock config so the UI shows something
                session.add(AiModelConfig(
                    user_id=admin.id,
                    name="麒麟AI助手",
                    provider="custom",
                    model="qilin-secops-ai",
                    api_url=None,
                    api_key=None,
                    temperature=0.3,
                    max_tokens=4096,
                    system_prompt="你是一个安全运维AI助手，基于麒麟操作系统安全运维平台的数据为用户提供专业分析和建议。",
                    is_active=1,
                    is_default=1,
                ))

        await session.commit()


async def drop_db():
    """Drop all tables (for development/testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
