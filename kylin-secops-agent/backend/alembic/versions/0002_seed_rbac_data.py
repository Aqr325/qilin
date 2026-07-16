"""0002_seed_rbac_data.py — 注入角色和权限种子数据

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-23 20:00:01.000000
"""
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

import sqlalchemy as sa
from alembic import op
from datetime import datetime, timezone
from app.core.security import hash_password


def upgrade() -> None:
    conn = op.get_bind()

    # ── Seed Permissions ──
    permissions = [
        # Agent
        ("agent:read", "查看Agent", "agent", "read"),
        ("agent:write", "管理Agent", "agent", "write"),
        ("agent:upgrade", "升级Agent", "agent", "upgrade"),
        ("agent:restart", "重启Agent", "agent", "restart"),
        # Alert
        ("alert:read", "查看告警", "alert", "read"),
        ("alert:write", "处置告警", "alert", "write"),
        ("alert:delete", "删除告警", "alert", "delete"),
        ("alert:assign", "指派告警", "alert", "assign"),
        ("alert:suppress", "抑制告警", "alert", "suppress"),
        ("alert:export", "导出告警", "alert", "export"),
        # Policy
        ("policy:read", "查看策略", "policy", "read"),
        ("policy:write", "管理策略", "policy", "write"),
        ("policy:delete", "删除策略", "policy", "delete"),
        ("policy:deploy", "下发策略", "policy", "deploy"),
        # System
        ("system:read", "查看系统", "system", "read"),
        ("system:write", "管理系统", "system", "write"),
        ("user:manage", "用户管理", "system", "user_manage"),
        ("role:manage", "角色管理", "system", "role_manage"),
        # Audit
        ("audit:read", "查看审计", "audit", "read"),
        # AI
        ("ai:read", "AI对话查看", "ai", "read"),
        ("ai:write", "AI对话操作", "ai", "write"),
        # Dashboard
        ("dashboard:read", "查看仪表盘", "dashboard", "read"),
        # Local Status
        ("local_status:read", "查看本机状态", "local_status", "read"),
    ]

    perm_ids = []
    for code, name, module, action in permissions:
        result = conn.execute(
            op.get_bind().dialect.statement_compiler(
                op.get_bind(), sa.text(
                    f"INSERT INTO permissions (code, name, module, action) "
                    f"VALUES ('{code}', '{name}', '{module}', '{action}') "
                    f"ON CONFLICT (code) DO NOTHING RETURNING id"
                )
            )
        )
        # Simpler approach: use text
        conn.execute(
            sa.text(
                "INSERT INTO permissions (code, name, module, action) "
                "VALUES (:code, :name, :module, :action) "
                "ON CONFLICT (code) DO NOTHING"
            ),
            {"code": code, "name": name, "module": module, "action": action},
        )

    # ── Seed Roles ──
    roles = [
        ("admin", "管理员", "系统管理员，拥有所有权限"),
        ("operator", "运维员", "安全运维工程师，可管理Agent和告警"),
        ("auditor", "审计员", "审计员，可查看告警和审计日志"),
        ("readonly", "只读用户", "只读用户，仅可查看基本信息"),
    ]

    role_ids = {}
    for name, display_name, description in roles:
        result = conn.execute(
            sa.text(
                "INSERT INTO roles (name, display_name, description, is_system) "
                "VALUES (:name, :display_name, :description, TRUE) "
                "ON CONFLICT (name) DO NOTHING RETURNING id"
            ),
            {"name": name, "display_name": display_name, "description": description},
        )
        row = result.fetchone()
        if row:
            role_ids[name] = row[0]

    # If roles already exist, fetch them
    if not role_ids:
        result = conn.execute(sa.text("SELECT name, id FROM roles"))
        for row in result:
            role_ids[row[0]] = row[1]

    # ── Assign Permissions to Roles ──
    admin_perms = [p[0] for p in permissions]
    operator_perms = [
        "agent:read", "agent:write", "agent:upgrade", "agent:restart",
        "alert:read", "alert:write", "alert:assign", "alert:suppress",
        "policy:read", "policy:write", "policy:delete", "policy:deploy",
        "dashboard:read",
        "ai:read", "ai:write",
        "local_status:read",
    ]
    auditor_perms = [
        "alert:read", "alert:export",
        "agent:read",
        "policy:read",
        "audit:read",
        "dashboard:read",
        "ai:read",
        "system:read",
        "local_status:read",
    ]
    readonly_perms = [
        "agent:read",
        "alert:read",
        "policy:read",
        "dashboard:read",
        "audit:read",
        "ai:read",
        "local_status:read",
    ]

    role_perm_map = {
        "admin": admin_perms,
        "operator": operator_perms,
        "auditor": auditor_perms,
        "readonly": readonly_perms,
    }

    for role_name, perm_codes in role_perm_map.items():
        role_id = role_ids.get(role_name)
        if not role_id:
            continue
        for code in perm_codes:
            conn.execute(
                sa.text(
                    "INSERT INTO role_permissions (role_id, permission_id) "
                    "SELECT :role_id, id FROM permissions WHERE code = :code "
                    "ON CONFLICT DO NOTHING"
                ),
                {"role_id": role_id, "code": code},
            )

    # ── Seed Admin User ──
    admin_password = hash_password("Kylin@2026!Secure")
    conn.execute(
        sa.text(
            "INSERT INTO users (username, password_hash, display_name, email, is_active) "
            "VALUES ('admin', :pwd, '系统管理员', 'admin@kylin-secops.com', TRUE) "
            "ON CONFLICT (username) DO NOTHING"
        ),
        {"pwd": admin_password},
    )

    # Assign admin role
    admin_role_id = role_ids.get("admin")
    conn.execute(
        sa.text(
            "INSERT INTO user_roles (user_id, role_id) "
            "SELECT id, :role_id FROM users WHERE username = 'admin' "
            "ON CONFLICT DO NOTHING"
        ),
        {"role_id": admin_role_id},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("DELETE FROM user_roles"))
    conn.execute(sa.text("DELETE FROM users WHERE username = 'admin'"))
    conn.execute(sa.text("DELETE FROM role_permissions"))
    conn.execute(sa.text("DELETE FROM permissions"))
    conn.execute(sa.text("DELETE FROM roles"))