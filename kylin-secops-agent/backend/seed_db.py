"""Database seed script for麒麟OS安全智能运维Agent.

Inserts default users, roles, and permissions into the database.
Designed for desktop deployment — standalone, no external ORM dependency
beyond SQLAlchemy async.

Usage:
    python seed_db.py
"""

import os
import sys

# ── Ensure backend/ is on the import path ──
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EXE_DIR = os.environ.get("EXE_DIR", SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import text as sa_text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.security import hash_password
from app.models.base import Base


def _get_db_url():
    """Get the database URL — respect EXE_DIR for desktop builds."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite"):
        # Extract path from sqlite URL
        path = url.replace("sqlite+aiosqlite:///", "")
        if not os.path.isabs(path):
            path = os.path.join(EXE_DIR, path)
        return f"sqlite+aiosqlite:///{os.path.abspath(path)}"
    return url


DB_URL = _get_db_url()
engine = create_async_engine(DB_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def seed_db():
    """Insert seed data: roles, permissions, users, and role-permission mappings."""
    # Import seed definitions
    from app.core.permissions import (
        Permission as PermissionEnum,
        DEFAULT_SEED_USERS,
        ROLE_PERMISSIONS,
        _resolve_seed_password,
    )

    _all_perms = sorted([p.value for p in PermissionEnum])
    display_names = {
        "admin": "管理员",
        "operator": "操作员",
        "auditor": "审计员",
        "readonly": "只读用户",
    }

    async with SessionLocal() as session:
        # ── 1. Seed Permissions ──
        existing_perm_codes = set()
        result = await session.execute(
            sa_text("SELECT code FROM permissions")
        )
        for row in result:
            existing_perm_codes.add(row[0])

        for code in _all_perms:
            if code not in existing_perm_codes:
                parts = code.split(":", 1)
                await session.execute(
                    sa_text("""
                        INSERT INTO permissions (id, code, name, module, action, created_at, updated_at)
                        VALUES (:id, :code, :name, :module, :action, :created_at, :updated_at)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "code": code,
                        "name": parts[1].replace("_", " ").title(),
                        "module": parts[0],
                        "action": parts[1],
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
        await session.flush()

        # ── 2. Seed Roles ──
        existing_role_names = set()
        result = await session.execute(
            sa_text("SELECT name FROM roles")
        )
        for row in result:
            existing_role_names.add(row[0])

        for role_name in ROLE_PERMISSIONS:
            if role_name not in existing_role_names:
                await session.execute(
                    sa_text("""
                        INSERT INTO roles (id, name, display_name, is_system, created_at, updated_at)
                        VALUES (:id, :name, :display_name, 1, :created_at, :updated_at)
                    """),
                    {
                        "id": str(uuid.uuid4()),
                        "name": role_name,
                        "display_name": display_names.get(role_name, role_name),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc),
                    },
                )
        await session.flush()

        # Reload roles
        result = await session.execute(sa_text("SELECT id, name FROM roles"))
        role_map = {row[1]: row[0] for row in result}

        # ── 3. Assign Permissions to Roles ──
        # Reload permissions
        result = await session.execute(sa_text("SELECT id, code FROM permissions"))
        perm_map = {row[1]: row[0] for row in result}

        for role_name, perm_codes in ROLE_PERMISSIONS.items():
            role_id = role_map.get(role_name)
            if not role_id:
                continue
            for code in perm_codes:
                perm_id = perm_map.get(code)
                if perm_id:
                    await session.execute(
                        sa_text("""
                            INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
                            VALUES (:role_id, :permission_id)
                        """),
                        {"role_id": role_id, "permission_id": perm_id},
                    )

        # ── 4. Seed Default Users ──
        existing_usernames = set()
        result = await session.execute(sa_text("SELECT username FROM users"))
        for row in result:
            existing_usernames.add(row[0])

        for su in DEFAULT_SEED_USERS:
            if su["username"] in existing_usernames:
                continue

            user_id = str(uuid.uuid4())
            role_name = su["role"]

            await session.execute(
                sa_text("""
                    INSERT INTO users (id, username, password_hash, display_name, email,
                                       is_active, created_at, updated_at,
                                       password_changed_at, login_attempts,
                                       must_change_password)
                    VALUES (:id, :username, :password_hash, :display_name, :email,
                            1, :created_at, :updated_at, :created_at, 0,
                            1)
                """),
                {
                    "id": user_id,
                    "username": su["username"],
                    "password_hash": hash_password(_resolve_seed_password(su["username"])),
                    "display_name": su["display_name"],
                    "email": su["email"],
                    "created_at": datetime.now(timezone.utc),
                },
            )

            # Link user to role
            role_id = role_map.get(role_name)
            if role_id:
                await session.execute(
                    sa_text("""
                        INSERT OR IGNORE INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                    """),
                    {"user_id": user_id, "role_id": role_id},
                )

        await session.commit()

        print("✅ Seed data inserted successfully!")
        print(f"   - Permissions: {len(perm_map)}")
        print(f"   - Roles: {len(role_map)}")
        print(f"   - Default users seeded: {len(DEFAULT_SEED_USERS)}")

    # Cleanup
    await engine.dispose()


async def ensure_indexes():
    """Create additional indexes for high-frequency queries."""
    indexes = [
        ("users", "role_id", "ix_users_role_id"),
        ("user_roles", "user_id, role_id", "ix_user_roles_user_id_role_id"),
        ("agents", "status", "ix_agents_status"),
        ("alerts", "severity, status", "ix_alerts_severity_status"),
        ("alerts", "status", "ix_alerts_status"),
        ("agent_heartbeats", "agent_id, received_at", "ix_agent_heartbeats_agent_time"),
        ("agent_heartbeats", "received_at", "ix_agent_heartbeats_received_at"),
        ("audit_logs", "action, resource_type, created_at", "ix_audit_logs_action_resource_time"),
        ("audit_logs", "user_id, created_at", "ix_audit_logs_user_id_created_at"),
        ("login_logs", "username, login_at", "ix_login_logs_username_login_at"),
        ("login_logs", "ip_address, login_at", "ix_login_logs_ip_login_at"),
        ("policies", "policy_type, status", "ix_policies_type_status"),
        ("policies", "status", "ix_policies_status"),
        ("policy_targets", "policy_id, agent_id", "ix_policy_targets_policy_agent"),
        ("policy_targets", "agent_id, status", "ix_policy_targets_agent_status"),
    ]

    async with engine.begin() as conn:
        for table, cols, name in indexes:
            sql = f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})"
            try:
                await conn.execute(sa_text(sql))
            except Exception as e:
                pass  # Ignore existing index errors

    print(f"✅ Ensured {len(indexes)} indexes")


async def main():
    """Main entry point: create tables → ensure indexes → seed data."""
    print(f"📁 Database: {DB_URL}")

    # Create tables first
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")

    await ensure_indexes()
    await seed_db()


if __name__ == "__main__":
    asyncio.run(main())