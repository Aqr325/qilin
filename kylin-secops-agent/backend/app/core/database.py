"""Database engine and session management."""

from typing import AsyncGenerator, Optional

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import settings


# ── Async Engine ──
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    echo=settings.DB_ECHO,
    pool_pre_ping=True,
    # For async with partitioned tables
    connect_args={
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    },
)

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


# ── Dependency ──
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that provides an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
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
        if self.session:
            if exc_type is None:
                await self.session.commit()
            else:
                await self.session.rollback()
            await self.session.close()


async def init_db():
    """Create all tables and seed default roles/permissions/users."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed roles, permissions, and default users on first run
    from datetime import datetime, timezone
    import uuid as _uuid

    from sqlalchemy import select, func

    # Import the Permission ENUM (not the SQLAlchemy model)
    from app.core.permissions import (
        Permission as PermissionEnum,
        DEFAULT_SEED_USERS,
        ROLE_PERMISSIONS,
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
                    password_hash=hash_password(su["password"]),
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

        await session.commit()


async def drop_db():
    """Drop all tables (for development/testing)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
