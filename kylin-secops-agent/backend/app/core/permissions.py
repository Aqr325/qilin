"""RBAC permissions system."""

from enum import Enum
from functools import wraps
from typing import Callable, List, Optional

from fastapi import Depends, HTTPException, status
from jose import JWTError

from app.core.security import decode_token


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


# ── Role Definitions ──
DEFAULT_SEED_USERS = [
    {
        "username": "admin",
        "password": "admin123",
        "display_name": "系统管理员",
        "email": "admin@kylin-secops.local",
        "role": "admin",
    },
    {
        "username": "operator",
        "password": "operator123",
        "display_name": "运维操作员",
        "email": "operator@kylin-secops.local",
        "role": "operator",
    },
    {
        "username": "auditor",
        "password": "auditor123",
        "display_name": "安全审计员",
        "email": "auditor@kylin-secops.local",
        "role": "auditor",
    },
    {
        "username": "viewer",
        "password": "viewer123",
        "display_name": "查看者",
        "email": "viewer@kylin-secops.local",
        "role": "readonly",
    },
]

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
        Permission.DASHBOARD_READ.value,
        Permission.AI_READ.value,
        Permission.AI_WRITE.value,
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
    ],
    "readonly": [
        Permission.AGENT_READ.value,
        Permission.ALERT_READ.value,
        Permission.POLICY_READ.value,
        Permission.DASHBOARD_READ.value,
        Permission.AUDIT_READ.value,
        Permission.AI_READ.value,
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
# (the actual implementation is in dependencies.py)

class CurrentUser:
    """Placeholder for type hints. The actual dependency is in api/deps.py."""


def get_current_user():
    """Placeholder - actual implementation in api/deps.py."""
    pass
