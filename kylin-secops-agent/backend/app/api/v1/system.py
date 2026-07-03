"""System management routes: users, roles, audit logs, settings."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_pagination
from app.core.database import get_db
from app.schemas.common import ApiResponse, Page
from app.schemas.system import (
    AuditLogFilterParams,
    AuditLogItem,
    AuditStats,
    LoginLog,
    LoginLogFilterParams,
    LoginLogUpdate,
    RoleCreate,
    RoleDetail,
    RoleUpdate,
    SystemSettings,
    SystemSettingsUpdate,
    UserCreate,
    UserDetail,
    UserStatusUpdate,
    UserSummary,
    UserUpdate,
)
from app.services import system_service

router = APIRouter(prefix="/system", tags=["系统管理"])


# ── User Management ──

@router.post("/users", response_model=ApiResponse[UserDetail], status_code=201)
async def create_user(
    req: UserCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建用户."""
    result = await system_service.create_user(db, req, operator=current_user)
    return ApiResponse(data=result, message="用户创建成功")


@router.get("/users", response_model=ApiResponse[Page[UserSummary]])
async def list_users(
    page: dict = Depends(get_pagination),
    role: str = Query(None),
    status: str = Query(None),
    keyword: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户列表."""
    result = await system_service.list_users(
        db, page=page["page"], size=page["size"],
        role=role, status=status, keyword=keyword,
    )
    return ApiResponse(data=result)


@router.get("/users/{user_id}", response_model=ApiResponse[UserDetail])
async def get_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """用户详情."""
    result = await system_service.get_user_detail(db, user_id)
    return ApiResponse(data=result)


@router.put("/users/{user_id}", response_model=ApiResponse[UserDetail])
async def update_user(
    user_id: str,
    req: UserUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户."""
    result = await system_service.update_user(db, user_id, req, operator=current_user)
    return ApiResponse(data=result)


@router.delete("/users/{user_id}", response_model=ApiResponse)
async def delete_user(
    user_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除用户."""
    await system_service.delete_user(db, user_id, operator=current_user)
    return ApiResponse(message="用户已删除")


@router.put("/users/{user_id}/status", response_model=ApiResponse[UserDetail])
async def toggle_user_status(
    user_id: str,
    req: UserStatusUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """启用/禁用用户."""
    result = await system_service.toggle_user_status(
        db, user_id, req.is_active, operator=current_user,
    )
    return ApiResponse(data=result)


# ── Role Management ──

@router.get("/roles", response_model=ApiResponse[list[RoleDetail]])
async def list_roles(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """角色列表."""
    result = await system_service.list_roles(db)
    return ApiResponse(data=result)


@router.get("/roles/{role_id}", response_model=ApiResponse[RoleDetail])
async def get_role(
    role_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """角色详情."""
    result = await system_service.get_role_detail(db, role_id)
    return ApiResponse(data=result)


@router.post("/roles", response_model=ApiResponse[RoleDetail], status_code=201)
async def create_role(
    req: RoleCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建角色."""
    result = await system_service.create_role(db, req, operator=current_user)
    return ApiResponse(data=result, message="角色创建成功")


@router.put("/roles/{role_id}", response_model=ApiResponse[RoleDetail])
async def update_role(
    role_id: str,
    req: RoleUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新角色权限."""
    result = await system_service.update_role(db, role_id, req, operator=current_user)
    return ApiResponse(data=result)


@router.delete("/roles/{role_id}", response_model=ApiResponse)
async def delete_role(
    role_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除角色."""
    await system_service.delete_role(db, role_id, operator=current_user)
    return ApiResponse(message="角色已删除")


@router.get("/permissions", response_model=ApiResponse[list[dict]])
async def list_permissions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """权限清单."""
    result = await system_service.list_permissions(db)
    return ApiResponse(data=result)


# ── Audit & Login Logs ──

@router.get("/login-logs", response_model=ApiResponse[Page[LoginLog]])
async def list_login_logs(
    page: dict = Depends(get_pagination),
    user_id: str = Query(None),
    status: str = Query(None),
    ip_address: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """登录日志."""
    result = await system_service.list_login_logs(
        db, page=page["page"], size=page["size"],
        user_id=user_id, status=status, ip_address=ip_address,
        start_time=start_time, end_time=end_time,
    )
    return ApiResponse(data=result)


@router.patch("/login-logs/{log_id}", response_model=ApiResponse[LoginLog])
async def update_login_log(
    log_id: int,
    req: LoginLogUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新登录日志状态."""
    result = await system_service.update_login_log(db, log_id, req)
    return ApiResponse(data=result)


@router.get("/audit-logs", response_model=ApiResponse[Page[AuditLogItem]])
async def list_audit_logs(
    page: dict = Depends(get_pagination),
    user_id: str = Query(None),
    action: str = Query(None),
    resource_type: str = Query(None),
    start_time: str = Query(None),
    end_time: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """操作审计日志."""
    result = await system_service.list_audit_logs(
        db, page=page["page"], size=page["size"],
        user_id=user_id, action=action, resource_type=resource_type,
        start_time=start_time, end_time=end_time,
    )
    return ApiResponse(data=result)


@router.get("/audit-logs/stats", response_model=ApiResponse[AuditStats])
async def audit_logs_stats(
    time_range: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """审计统计."""
    result = await system_service.get_audit_stats(db, time_range)
    return ApiResponse(data=result)


# ── System Settings ──

@router.get("/settings", response_model=ApiResponse[SystemSettings])
async def get_settings(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """系统设置."""
    result = await system_service.get_settings(db)
    return ApiResponse(data=result)


@router.put("/settings", response_model=ApiResponse[SystemSettings])
async def update_settings(
    req: SystemSettingsUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新系统设置."""
    result = await system_service.update_settings(db, req, operator=current_user)
    return ApiResponse(data=result)