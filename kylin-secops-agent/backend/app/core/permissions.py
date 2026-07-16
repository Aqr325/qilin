"""RBAC permissions system."""

import logging
import os
import secrets

from enum import Enum
from functools import wraps
from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, status
from jose import JWTError

from app.core.security import decode_token

logger = logging.getLogger(__name__)


# ── Permission Codes ──
class Permission(str, Enum):
    """System permission codes."""

    # Agent
    AGENT_READ = "agent:read"
    AGENT_WRITE = "agent:write"
    AGENT_UPGRADE = "agent:upgrade"
    AGENT_RESTART = "agent:restart"

    # Alert
    ALERT_READ = "alert:read"
    ALERT_WRITE = "alert:write"
    ALERT_DELETE = "alert:delete"
    ALERT_ASSIGN = "alert:assign"
    ALERT_SUPPRESS = "alert:suppress"
    ALERT_EXPORT = "alert:export"

    # Policy
    POLICY_READ = "policy:read"
    POLICY_WRITE = "policy:write"
    POLICY_DELETE = "policy:delete"
    POLICY_DEPLOY = "policy:deploy"

    # System / Admin
    SYSTEM_READ = "system:read"
    SYSTEM_WRITE = "system:write"
    USER_MANAGE = "user:manage"
    ROLE_MANAGE = "role:manage"

    # Audit
    AUDIT_READ = "audit:read"

    # AI
    AI_READ = "ai:read"
    AI_WRITE = "ai:write"

    # Dashboard
    DASHBOARD_READ = "dashboard:read"

    # Local Status (server-side system monitoring)
    LOCAL_STATUS_READ = "local_status:read"


# ── Role Definitions ──
# Passwords are None by default — resolved at seed time via _resolve_seed_password().
# This prevents plaintext passwords from being committed to source control.
DEFAULT_SEED_USERS = [
    {
        "username": "admin",
        "password": None,  # Resolved at seed time
        "display_name": "系统管理员",
        "email": "admin@kylin-secops.local",
        "role": "admin",
    },
    {
        "username": "operator",
        "password": None,  # Resolved at seed time
        "display_name": "运维操作员",
        "email": "operator@kylin-secops.local",
        "role": "operator",
    },
    {
        "username": "auditor",
        "password": None,  # Resolved at seed time
        "display_name": "安全审计员",
        "email": "auditor@kylin-secops.local",
        "role": "auditor",
    },
    {
        "username": "viewer",
        "password": None,  # Resolved at seed time
        "display_name": "查看者",
        "email": "viewer@kylin-secops.local",
        "role": "readonly",
    },
]


def _resolve_seed_password(username: str) -> str:
    """Resolve a seed user's password at runtime.

    Priority:
    1. Environment variable KYLIN_SEED_PASSWORD (single shared password for all seed users)
    2. Per-user env var KYLIN_SEED_<USERNAME>_PASSWORD (e.g. KYLIN_SEED_ADMIN_PASSWORD)
    3. Auto-generated strong random password (24 chars URL-safe)

    In dev/debug mode, generated passwords are logged to stdout for first-time setup.
    """
    # 1. Global shared seed password
    global_pwd = os.environ.get("KYLIN_SEED_PASSWORD", "").strip()
    if global_pwd:
        return global_pwd

    # 2. Per-user seed password
    per_user_key = f"KYLIN_SEED_{username.upper()}_PASSWORD"
    per_user_pwd = os.environ.get(per_user_key, "").strip()
    if per_user_pwd:
        return per_user_pwd

    # 3. Auto-generated strong random password (24 chars)
    # NOTE: the generated password is intentionally NOT written to any log or
    # stdout — doing so would leak credentials. Operators retrieve it from the
    # local bootstrap file on first run (see seed logic), and all seed users
    # are flagged must_change_password to force a reset on first login.
    return secrets.token_urlsafe(24)

def _write_bootstrap_file(passwords: dict) -> None:
    """Persist initial seed passwords to a local file for first-run retrieval.

    Seed users are created with ``must_change_password=True`` and a per-install
    random password (when no KYLIN_SEED_PASSWORD is set). The only place the
    plaintext passwords are written down is this local file (0600), so the
    operator can log in once and is then forced to change them.
    """
    try:
        data_dir = os.path.join(os.getcwd(), "data")
        os.makedirs(data_dir, exist_ok=True)
        path = os.path.join(data_dir, "bootstrap.txt")
        lines = [
            "# 麒麟OS安全智能运维Agent 初始账户口令（首次登录后请立即修改）",
            "",
        ]
        for username, pwd in passwords.items():
            lines.append(f"{username}: {pwd}")
        with open(path, "w", encoding="utf-8") as _bf:
            _bf.write("\n".join(lines) + "\n")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    except OSError as e:
        logger.warning("无法写入 bootstrap.txt: %s", e)


ROLE_PERMISSIONS: dict[str, list[str]] = {
    "admin": [p.value for p in Permission],
    "operator": [
        Permission.AGENT_READ.value,
        Permission.AGENT_WRITE.value,
        Permission.AGENT_UPGRADE.value,
        Permission.AGENT_RESTART.value,
        Permission.ALERT_READ.value,
        Permission.ALERT_WRITE.value,
        Permission.ALERT_ASSIGN.value,
        Permission.ALERT_SUPPRESS.value,
        Permission.POLICY_READ.value,
        Permission.POLICY_WRITE.value,
        Permission.POLICY_DELETE.value,
        Permission.POLICY_DEPLOY.value,
        Permission.DASHBOARD_READ.value,
        Permission.AI_READ.value,
        Permission.AI_WRITE.value,
        Permission.LOCAL_STATUS_READ.value,
    ],
    "auditor": [
        Permission.ALERT_READ.value,
        Permission.ALERT_EXPORT.value,
        Permission.AGENT_READ.value,
        Permission.POLICY_READ.value,
        Permission.AUDIT_READ.value,
        Permission.DASHBOARD_READ.value,
        Permission.AI_READ.value,
        Permission.SYSTEM_READ.value,
        Permission.LOCAL_STATUS_READ.value,
    ],
    "readonly": [
        Permission.AGENT_READ.value,
        Permission.ALERT_READ.value,
        Permission.POLICY_READ.value,
        Permission.DASHBOARD_READ.value,
        Permission.AUDIT_READ.value,
        Permission.AI_READ.value,
        Permission.LOCAL_STATUS_READ.value,
    ],
}

# Role hierarchy for inheritance
ROLE_HIERARCHY: dict[str, list[str]] = {
    "admin": ["operator", "auditor", "readonly"],
    "operator": ["readonly"],
    "auditor": ["readonly"],
    "readonly": [],
}


# ── Permission Checker ──

def check_permission(user_permissions: List[str], required: str) -> bool:
    """Check if user has a specific permission."""
    return required in user_permissions


def check_any_permission(user_permissions: List[str], required: List[str]) -> bool:
    """Check if user has any of the required permissions."""
    return any(p in user_permissions for p in required)


def check_all_permissions(user_permissions: List[str], required: List[str]) -> bool:
    """Check if user has all of the required permissions."""
    return all(p in user_permissions for p in required)


# ── Dependency: require a specific permission ──

def require_permission(permission: Permission):
    """Dependency that verifies the current user has a specific permission.

    Usage:
        @router.get("/agents")
        async def list_agents(
            current_user = Depends(require_permission(Permission.AGENT_READ))
        ):
            ...
    """

    async def permission_checker(
        current_user: "CurrentUser" = Depends(get_current_user),  # type: ignore
    ):
        if not current_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Not authenticated",
            )
        user_perms = current_user.get("permissions", [])
        if permission.value not in user_perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {permission.value}",
            )
        return current_user

    return permission_checker


# ── Role-based decorator ──

def require_roles(roles: List[str]):
    """Decorator that restricts access to specific roles.

    Usage:
        @router.get("/system/users")
        @require_roles(["admin"])
        async def list_users():
            ...
    """

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            current_user = kwargs.get("current_user")
            if not current_user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                )
            user_roles = [r.get("name") for r in current_user.get("roles", [])]
            if not any(r in roles for r in user_roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Insufficient role privileges",
                )
            return await func(*args, **kwargs)

        return wrapper

    return decorator


# ── Get current user from request ──
# The real implementation lives in api/deps.py. Re-export it here so that
# require_permission() (and any other caller in this module) resolves to the
# working dependency instead of a no-op placeholder. Without this, every
# permission-guarded route returned 401 because Depends(get_current_user)
# bound to the placeholder, which always returned None.

from app.api.deps import get_current_user  # noqa: E402


class CurrentUser:
    """Placeholder for type hints. The actual dependency is in api/deps.py."""
