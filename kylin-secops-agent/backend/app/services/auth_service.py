"""Auth service: login, token management, password operations."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_token_pair,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.audit import LoginLog
from app.models.user import User
from app.repositories.user_repo import UserRepository, PermissionRepository
from app.schemas.auth import LoginResponse, UserProfile
from app.schemas.common import ApiResponse


def parse_time_range(time_range: str) -> Optional[datetime]:
    """Parse time range string to datetime."""
    now = datetime.now(timezone.utc)
    ranges = {
        "1h": timedelta(hours=1),
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    if time_range in ranges:
        return now - ranges[time_range]
    return None


async def login(
    db: AsyncSession,
    username: str,
    password: str,
    mfa_code: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> dict:
    """Authenticate user and return tokens."""
    user_repo = UserRepository(db)

    # 对目标用户行加锁（SELECT ... FOR UPDATE），避免并发登录竞态导致锁计数器错乱
    result = await db.execute(
        select(User).where(User.username == username).with_for_update()
    )
    user = result.scalar_one_or_none()
    if not user:
        await _record_login_log(db, username, "failed", ip_address, user_agent,
                                failure_reason="user_not_found")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )

    # Check if locked
    if user.is_locked:
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            remaining = int((user.locked_until - datetime.now(timezone.utc)).total_seconds() / 60)
            await _record_login_log(db, username, "locked", ip_address, user_agent,
                                    user_id=str(user.id))
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail=f"账户已被锁定，请{remaining}分钟后重试",
            )
        else:
            user.is_locked = False
            user.login_attempts = 0
            await db.flush()

    # Verify password
    if not verify_password(password, user.password_hash):
        await user_repo.increment_login_attempts(user.id)
        remaining = settings.MAX_LOGIN_ATTEMPTS - user.login_attempts
        await _record_login_log(db, username, "failed", ip_address, user_agent,
                                user_id=str(user.id), failure_reason="wrong_password")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"用户名或密码错误，剩余重试次数: {max(0, remaining)}",
        )

    # Check if active
    if not user.is_active:
        await _record_login_log(db, username, "failed", ip_address, user_agent,
                                user_id=str(user.id), failure_reason="account_disabled")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用",
        )

    # Update last login
    await user_repo.update_last_login(user.id, ip_address)

    # Generate tokens
    extra_claims = {
        "username": user.username,
        "roles": [r.name for r in user.roles],
    }
    tokens = create_token_pair(str(user.id), extra_claims)

    # Record login success
    await _record_login_log(db, username, "success", ip_address, user_agent,
                            user_id=str(user.id))

    return {
        **tokens,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "display_name": user.display_name,
            "email": user.email,
            "phone": user.phone,
            "is_active": user.is_active,
            "is_locked": user.is_locked,
            "mfa_enabled": user.mfa_enabled,
            "last_login_at": user.last_login_at,
            "last_login_ip": user.last_login_ip,
            "password_changed_at": user.password_changed_at,
            "roles": user.role_list,
            "permissions": user.permission_list,
            "created_at": user.created_at,
        },
    }


async def refresh_token(db: AsyncSession, refresh_token_str: str) -> dict:
    """Refresh access token using refresh token."""
    try:
        payload = decode_token(refresh_token_str)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired or invalid",
        )

    # Verify user still exists
    user_repo = UserRepository(db)
    user = await user_repo.get(uuid.UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or disabled",
        )

    extra_claims = {
        "username": user.username,
        "roles": [r.name for r in user.roles],
    }
    new_tokens = create_token_pair(str(user.id), extra_claims)
    return new_tokens


async def logout(current_user: dict) -> None:
    """Logout current user."""
    # In production: add refresh_token to Redis blacklist
    current_user["_logged_out_at"] = datetime.now(timezone.utc).isoformat()


async def change_password(
    db: AsyncSession,
    user_id: str,
    old_password: str,
    new_password: str,
) -> None:
    """Change user password."""
    user_repo = UserRepository(db)
    user = await user_repo.get(uuid.UUID(user_id))

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if not verify_password(old_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="旧密码不正确",
        )

    if len(new_password) < settings.PASSWORD_MIN_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"密码长度不能少于{settings.PASSWORD_MIN_LENGTH}位",
        )

    user.password_hash = hash_password(new_password)
    user.password_changed_at = datetime.now(timezone.utc)
    await db.flush()


async def get_user_permissions(db: AsyncSession, user_id: str) -> List[dict]:
    """Get permissions for a user."""
    user_repo = UserRepository(db)
    user = await user_repo.get_with_roles(uuid.UUID(user_id))
    if not user:
        return []

    perms = user.permission_list
    perm_repo = PermissionRepository(db)
    all_perms = []
    for code in perms:
        perm = await perm_repo.get_by_code(code)
        if perm:
            all_perms.append({
                "code": perm.code,
                "name": perm.name,
                "module": perm.module,
                "action": perm.action,
                "description": perm.description,
            })
    return all_perms


async def update_user_profile(
    db: AsyncSession,
    user_id: str,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
) -> dict:
    """Update user profile information."""
    from app.models.user import User
    from uuid import UUID

    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if display_name is not None:
        user.display_name = display_name
    if email is not None:
        user.email = email
    if phone is not None:
        user.phone = phone

    await db.commit()
    await db.refresh(user)

    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "mfa_enabled": user.mfa_enabled,
        "last_login_at": user.last_login_at,
        "roles": [],
        "permissions": [],
        "created_at": user.created_at,
    }


async def toggle_mfa(
    db: AsyncSession,
    user_id: str,
    enabled: bool,
) -> dict:
    """Toggle MFA for a user."""
    from app.models.user import User
    from uuid import UUID

    stmt = select(User).where(User.id == UUID(user_id))
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    user.mfa_enabled = enabled
    await db.commit()
    await db.refresh(user)

    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "phone": user.phone,
        "is_active": user.is_active,
        "mfa_enabled": user.mfa_enabled,
        "last_login_at": user.last_login_at,
        "roles": [],
        "permissions": [],
        "created_at": user.created_at,
    }


async def _record_login_log(
    db: AsyncSession,
    username: str,
    status_str: str,
    ip_address: Optional[str],
    user_agent: Optional[str],
    user_id: Optional[str] = None,
    failure_reason: Optional[str] = None,
):
    """Record login attempt to log."""
    log = LoginLog(
        user_id=uuid.UUID(user_id) if user_id else None,
        username=username,
        status=status_str,
        failure_reason=failure_reason,
        ip_address=ip_address or "0.0.0.0",
        user_agent=user_agent,
        auth_method="password",
    )
    db.add(log)
    await db.flush()