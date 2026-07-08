"""System service: user/role management, audit logs, settings."""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User, Role, Permission, user_roles, role_permissions
from app.models.audit import LoginLog as LoginLogModel
from app.models.settings import SystemSetting
from app.repositories.user_repo import UserRepository, RoleRepository, PermissionRepository
from app.repositories.audit_repo import AuditLogRepository, LoginLogRepository
from app.schemas.common import Page
from app.schemas.system import (
    AuditLogItem,
    AuditStats,
    LoginLog,
    LoginLogUpdate,
    RoleCreate,
    RoleDetail,
    RoleUpdate,
    SystemSettings,
    SystemSettingsUpdate,
    UserCreate,
    UserDetail,
    UserSummary,
    UserUpdate,
)


async def create_user(
    db: AsyncSession,
    req: UserCreate,
    operator: dict,
) -> UserDetail:
    """Create a new user."""
    user_repo = UserRepository(db)

    existing = await user_repo.get_by_username(req.username)
    if existing:
        raise HTTPException(status_code=409, detail="用户名已存在")

    existing_email = await user_repo.get_by_email(req.email)
    if existing_email:
        raise HTTPException(status_code=409, detail="邮箱已存在")

    user = User(
        username=req.username,
        password_hash=hash_password(req.password),
        display_name=req.display_name,
        email=req.email,
        phone=req.phone,
        is_active=req.is_active,
    )
    db.add(user)
    await db.flush()

    # Assign roles
    role_repo = RoleRepository(db)

    # If role name provided, resolve to role IDs
    role_ids_to_assign: List[str] = list(req.role_ids)
    if req.role and not req.role_ids:
        role_obj = await role_repo.get_by_name(req.role)
        if role_obj:
            role_ids_to_assign = [str(role_obj.id)]

    for role_id in role_ids_to_assign:
        role = await role_repo.get(uuid.UUID(role_id))
        if role:
            await db.execute(
                user_roles.insert().values(
                    user_id=user.id,
                    role_id=role.id,
                    granted_by=uuid.UUID(operator["id"]),
                )
            )

    await db.flush()
    # 角色通过原始SQL写入，需刷新关系集合，否则返回的 role_list 为空
    await db.refresh(user, ['roles'])
    return await _user_to_detail(user)


async def list_users(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    role: Optional[str] = None,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
) -> Page[UserSummary]:
    """List users with pagination."""
    user_repo = UserRepository(db)
    skip = (page - 1) * size
    filters = {"is_deleted": False}
    if status == "active":
        filters["is_active"] = True
    elif status == "disabled":
        filters["is_active"] = False

    users, total = await user_repo.get_multi(
        skip=skip, limit=size,
        order_by="created_at", order_desc=True,
        filters=filters,
    )

    items = [
        UserSummary(
            id=str(u.id),
            username=u.username,
            display_name=u.display_name,
            email=u.email,
            phone=u.phone,
            is_active=u.is_active,
            is_locked=u.is_locked,
            last_login_at=u.last_login_at,
            mfa_enabled=u.mfa_enabled,
            roles=u.role_list,
            created_at=u.created_at,
        )
        for u in users
    ]
    return Page.create(items, total, page, size)


async def get_user_detail(db: AsyncSession, user_id: str) -> UserDetail:
    """Get user detail."""
    user_repo = UserRepository(db)
    user = await user_repo.get_with_roles(uuid.UUID(user_id))
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="用户不存在")
    return await _user_to_detail(user)


async def update_user(
    db: AsyncSession,
    user_id: str,
    req: UserUpdate,
    operator: dict,
) -> UserDetail:
    """Update user."""
    user_repo = UserRepository(db)
    user = await user_repo.get(uuid.UUID(user_id))
    if not user or user.is_deleted:
        raise HTTPException(status_code=404, detail="用户不存在")

    update_data = req.model_dump(exclude_unset=True)
    role_ids = update_data.pop("role_ids", None)
    role_name = update_data.pop("role", None)

    for field, value in update_data.items():
        if hasattr(user, field):
            setattr(user, field, value)

    # Resolve role name to IDs
    role_ids_to_assign: Optional[List[str]] = role_ids
    if role_name and role_ids is None:
        role_repo = RoleRepository(db)
        role_obj = await role_repo.get_by_name(role_name)
        if role_obj:
            role_ids_to_assign = [str(role_obj.id)]

    # Update roles if provided
    if role_ids_to_assign is not None:
        # Remove existing roles
        await db.execute(
            user_roles.delete().where(user_roles.c.user_id == user.id)
        )
        # Add new roles
        role_repo = RoleRepository(db)
        for rid in role_ids_to_assign:
            role = await role_repo.get(uuid.UUID(rid))
            if role:
                await db.execute(
                    user_roles.insert().values(
                        user_id=user.id,
                        role_id=role.id,
                        granted_by=uuid.UUID(operator["id"]),
                    )
                )

    await db.flush()
    await db.refresh(user, ['roles'])
    return await _user_to_detail(user)


async def delete_user(db: AsyncSession, user_id: str, operator: dict):
    """Delete user (soft delete)."""
    user_repo = UserRepository(db)
    user = await user_repo.get(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_deleted = True
    user.deleted_at = datetime.now(timezone.utc)
    await db.flush()


async def toggle_user_status(
    db: AsyncSession,
    user_id: str,
    is_active: bool,
    operator: dict,
) -> UserDetail:
    """Enable/disable user."""
    user_repo = UserRepository(db)
    user = await user_repo.get(uuid.UUID(user_id))
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = is_active
    await db.flush()
    await db.refresh(user, ['roles'])
    return await _user_to_detail(user)


async def list_roles(db: AsyncSession) -> List[RoleDetail]:
    """List all roles."""
    role_repo = RoleRepository(db)
    roles = await role_repo.list_all()
    return [
        RoleDetail(
            id=str(r.id),
            name=r.name,
            display_name=r.display_name,
            description=r.description,
            is_system=r.is_system,
            permissions=[
                {"id": str(p.id), "code": p.code, "name": p.name}
                for p in r.permissions
            ],
            created_at=r.created_at,
        )
        for r in roles
    ]


async def get_role_detail(db: AsyncSession, role_id: str) -> RoleDetail:
    """角色详情."""
    role_repo = RoleRepository(db)
    role = await role_repo.get(uuid.UUID(role_id))
    if not role or role.is_deleted:
        raise HTTPException(status_code=404, detail="角色不存在")
    return RoleDetail(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            {"id": str(p.id), "code": p.code, "name": p.name}
            for p in role.permissions
        ],
        created_at=role.created_at,
    )


async def create_role(
    db: AsyncSession,
    req: RoleCreate,
    operator: dict,
) -> RoleDetail:
    """Create a new role."""
    role_repo = RoleRepository(db)
    existing = await role_repo.get_by_name(req.name)
    if existing:
        raise HTTPException(status_code=409, detail="角色名称已存在")

    role = Role(
        name=req.name,
        display_name=req.display_name,
        description=req.description,
    )
    db.add(role)
    await db.flush()

    # Assign permissions
    perm_repo = PermissionRepository(db)
    for perm_id in req.permission_ids:
        perm = await perm_repo.get(uuid.UUID(perm_id))
        if perm:
            await db.execute(
                role_permissions.insert().values(
                    role_id=role.id,
                    permission_id=perm.id,
                )
            )

    await db.flush()
    await db.refresh(role)

    return RoleDetail(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            {"id": str(p.id), "code": p.code, "name": p.name}
            for p in role.permissions
        ],
        created_at=role.created_at,
    )


async def update_role(
    db: AsyncSession,
    role_id: str,
    req: RoleUpdate,
    operator: dict,
) -> RoleDetail:
    """Update role permissions."""
    role_repo = RoleRepository(db)
    role = await role_repo.get(uuid.UUID(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")

    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可修改")

    if req.display_name is not None:
        role.display_name = req.display_name
    if req.description is not None:
        role.description = req.description

    if req.permission_ids is not None:
        # Remove existing permissions
        await db.execute(
            role_permissions.delete().where(role_permissions.c.role_id == role.id)
        )
        # Add new permissions
        perm_repo = PermissionRepository(db)
        for perm_id in req.permission_ids:
            perm = await perm_repo.get(uuid.UUID(perm_id))
            if perm:
                await db.execute(
                    role_permissions.insert().values(
                        role_id=role.id,
                        permission_id=perm.id,
                    )
                )

    await db.flush()
    await db.refresh(role)

    return RoleDetail(
        id=str(role.id),
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        is_system=role.is_system,
        permissions=[
            {"id": str(p.id), "code": p.code, "name": p.name}
            for p in role.permissions
        ],
        created_at=role.created_at,
    )


async def delete_role(db: AsyncSession, role_id: str, operator: dict):
    """Delete role."""
    role_repo = RoleRepository(db)
    role = await role_repo.get(uuid.UUID(role_id))
    if not role:
        raise HTTPException(status_code=404, detail="角色不存在")
    if role.is_system:
        raise HTTPException(status_code=400, detail="系统内置角色不可删除")
    await db.delete(role)
    await db.flush()


async def list_permissions(db: AsyncSession) -> List[dict]:
    """List all permissions."""
    perm_repo = PermissionRepository(db)
    perms, _ = await perm_repo.get_multi(limit=200)
    return [
        {
            "id": str(p.id),
            "code": p.code,
            "name": p.name,
            "module": p.module,
            "action": p.action,
            "description": p.description,
        }
        for p in perms
    ]


async def list_login_logs(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    ip_address: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Page[LoginLog]:
    """List login logs."""
    log_repo = LoginLogRepository(db)
    skip = (page - 1) * size
    logs, total = await log_repo.list_paginated(
        skip=skip, limit=size,
        user_id=user_id, status=status, ip_address=ip_address,
        start_time=start_time, end_time=end_time,
    )
    items = [
        LoginLog(
            id=log.id,
            username=log.username,
            status=log.status,
            failure_reason=log.failure_reason,
            ip_address=str(log.ip_address) if log.ip_address else "",
            user_agent=log.user_agent,
            auth_method=log.auth_method,
            login_at=log.login_at,
        )
        for log in logs
    ]
    return Page.create(items, total, page, size)


async def update_login_log(
    db: AsyncSession,
    log_id: str,
    req: LoginLogUpdate,
) -> LoginLog:
    """Update a login log's status/reason."""
    log_repo = LoginLogRepository(db)
    log = await log_repo.get(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Login log not found")
    update_data = req.model_dump(exclude_unset=True)
    if "id" in update_data:
        del update_data["id"]
    for key, value in update_data.items():
        setattr(log, key, value)
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return LoginLog(
        id=log.id,
        username=log.username,
        status=log.status,
        failure_reason=log.failure_reason,
        ip_address=str(log.ip_address) if log.ip_address else "",
        user_agent=log.user_agent,
        auth_method=log.auth_method,
        login_at=log.login_at,
    )


async def list_audit_logs(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    user_id: Optional[str] = None,
    action: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Page[AuditLogItem]:
    """List audit logs."""
    audit_repo = AuditLogRepository(db)
    skip = (page - 1) * size
    logs, total = await audit_repo.list_paginated(
        skip=skip, limit=size,
        user_id=user_id, action=action, resource_type=resource_type,
        start_time=start_time, end_time=end_time,
    )
    items = [
        AuditLogItem(
            id=log.id,
            username=log.username,
            action=log.action,
            resource_type=log.resource_type,
            resource_id=log.resource_id,
            resource_name=log.resource_name,
            detail=log.detail,
            ip_address=str(log.ip_address) if log.ip_address else None,
            user_agent=log.user_agent,
            duration_ms=log.duration_ms,
            result=log.result,
            error_message=log.error_message,
            created_at=log.created_at,
        )
        for log in logs
    ]
    return Page.create(items, total, page, size)


async def get_audit_stats(
    db: AsyncSession,
    time_range: Optional[str] = None,
) -> AuditStats:
    """Get audit statistics."""
    audit_repo = AuditLogRepository(db)
    stats = await audit_repo.get_stats(time_range)
    return AuditStats(**stats)


async def get_settings(db: AsyncSession) -> SystemSettings:
    """Get system settings from DB (single row)."""
    from sqlalchemy import select
    result = await db.execute(select(SystemSetting).limit(1))
    row = result.scalar_one_or_none()
    if not row:
        # Create default row
        row = SystemSetting()
        db.add(row)
        await db.commit()
        await db.refresh(row)
    return SystemSettings(
        mfa_enforced_roles=json.loads(row.mfa_enforced_roles) if row.mfa_enforced_roles else [],
        password_min_length=row.password_min_length,
        password_expire_days=row.password_expire_days,
        session_timeout_minutes=row.session_timeout_minutes,
        alert_auto_resolve_hours=row.alert_auto_resolve_hours,
        heartbeat_timeout_seconds=row.heartbeat_timeout_seconds,
        max_login_attempts=row.max_login_attempts,
        lockout_duration_minutes=row.lockout_duration_minutes,
        ai_auto_analysis=row.ai_auto_analysis,
        notification_enabled=row.notification_enabled,
    )


async def update_settings(
    db: AsyncSession,
    req: SystemSettingsUpdate,
    operator: dict,
) -> SystemSettings:
    """Update system settings in DB."""
    from sqlalchemy import select
    result = await db.execute(select(SystemSetting).limit(1))
    row = result.scalar_one_or_none()
    if not row:
        row = SystemSetting()
        db.add(row)
        await db.flush()
    update_data = req.model_dump(exclude_unset=True)
    if "mfa_enforced_roles" in update_data:
        update_data["mfa_enforced_roles"] = json.dumps(update_data["mfa_enforced_roles"])
    for key, value in update_data.items():
        if hasattr(row, key):
            setattr(row, key, value)
    await db.commit()
    await db.refresh(row)
    return SystemSettings(
        mfa_enforced_roles=json.loads(row.mfa_enforced_roles) if row.mfa_enforced_roles else [],
        password_min_length=row.password_min_length,
        password_expire_days=row.password_expire_days,
        session_timeout_minutes=row.session_timeout_minutes,
        alert_auto_resolve_hours=row.alert_auto_resolve_hours,
        heartbeat_timeout_seconds=row.heartbeat_timeout_seconds,
        max_login_attempts=row.max_login_attempts,
        lockout_duration_minutes=row.lockout_duration_minutes,
        ai_auto_analysis=row.ai_auto_analysis,
        notification_enabled=row.notification_enabled,
    )


async def _user_to_detail(user: User) -> UserDetail:
    """Convert User model to UserDetail schema."""
    return UserDetail(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        phone=user.phone,
        is_active=user.is_active,
        is_locked=user.is_locked,
        locked_until=user.locked_until,
        login_attempts=user.login_attempts,
        last_login_at=user.last_login_at,
        last_login_ip=str(user.last_login_ip) if user.last_login_ip else None,
        mfa_enabled=user.mfa_enabled,
        password_changed_at=user.password_changed_at,
        roles=user.role_list,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )