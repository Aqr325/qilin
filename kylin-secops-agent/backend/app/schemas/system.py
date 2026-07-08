"""System schemas: user management, roles, audit logs."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, EmailStr


# ── User Schemas ──

class UserCreate(BaseModel):
    """创建用户请求."""

    username: str = Field(..., min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    password: str = Field(..., min_length=12, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)
    email: str
    phone: Optional[str] = None
    role: Optional[str] = None  # Role name (admin/operator/auditor/readonly)
    role_ids: List[str] = Field(default_factory=list)  # Fallback: explicit UUIDs
    is_active: bool = True


class UserUpdate(BaseModel):
    """更新用户请求."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None  # Role name
    role_ids: Optional[List[str]] = None
    is_active: Optional[bool] = None


class UserSummary(BaseModel):
    """用户列表摘要."""

    id: str
    username: str
    display_name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_locked: bool
    last_login_at: Optional[datetime] = None
    mfa_enabled: bool = False
    roles: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class UserDetail(BaseModel):
    """用户详情."""

    id: str
    username: str
    display_name: str
    email: str
    phone: Optional[str] = None
    is_active: bool
    is_locked: bool
    locked_until: Optional[datetime] = None
    login_attempts: int = 0
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    mfa_enabled: bool = False
    password_changed_at: Optional[datetime] = None
    roles: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class UserStatusUpdate(BaseModel):
    """用户状态更新请求."""

    is_active: bool


# ── Role Schemas ──

class RoleCreate(BaseModel):
    """创建角色请求."""

    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    permission_ids: List[str] = Field(default_factory=list)


class RoleUpdate(BaseModel):
    """更新角色请求."""

    display_name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    permission_ids: Optional[List[str]] = None


class RoleDetail(BaseModel):
    """角色详情."""

    id: str
    name: str
    display_name: str
    description: Optional[str] = None
    is_system: bool = False
    permissions: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None


# ── Audit Log Schemas ──

class LoginLog(BaseModel):
    """登录日志."""

    id: str
    username: str
    status: str
    failure_reason: Optional[str] = None
    ip_address: str
    user_agent: Optional[str] = None
    auth_method: str = "password"
    login_at: Optional[datetime] = None


class LoginLogUpdate(BaseModel):
    """登录日志状态更新."""
    id: str
    status: Optional[str] = None
    failure_reason: Optional[str] = None


class AuditLogItem(BaseModel):
    """审计日志项."""

    id: int
    username: str
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    detail: Optional[Dict[str, Any]] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    duration_ms: Optional[int] = None
    result: str = "success"
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class AuditStats(BaseModel):
    """审计统计."""

    total: int = 0
    by_action: Dict[str, int] = Field(default_factory=dict)
    by_resource: Dict[str, int] = Field(default_factory=dict)
    by_user: List[Dict[str, Any]] = Field(default_factory=list)
    failure_rate: float = 0.0


# ── System Settings ──

class SystemSettings(BaseModel):
    """系统设置."""

    mfa_enforced_roles: List[str] = Field(default_factory=list)
    password_min_length: int = 12
    password_expire_days: int = 90
    session_timeout_minutes: int = 60
    alert_auto_resolve_hours: int = 72
    heartbeat_timeout_seconds: int = 30
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15
    ai_auto_analysis: bool = True
    notification_enabled: bool = True


class SystemSettingsUpdate(BaseModel):
    """系统设置更新请求."""

    mfa_enforced_roles: Optional[List[str]] = None
    password_min_length: Optional[int] = Field(None, ge=8, le=32)
    password_expire_days: Optional[int] = Field(None, ge=30, le=365)
    session_timeout_minutes: Optional[int] = Field(None, ge=15, le=1440)
    alert_auto_resolve_hours: Optional[int] = Field(None, ge=1, le=720)
    heartbeat_timeout_seconds: Optional[int] = Field(None, ge=10, le=120)
    max_login_attempts: Optional[int] = Field(None, ge=3, le=20)
    lockout_duration_minutes: Optional[int] = Field(None, ge=1, le=1440)
    ai_auto_analysis: Optional[bool] = None
    notification_enabled: Optional[bool] = None


# ── Filter Params ──

class LoginLogFilterParams(BaseModel):
    """登录日志筛选参数."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    user_id: Optional[str] = None
    username: Optional[str] = None
    status: Optional[str] = None
    ip_address: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class AuditLogFilterParams(BaseModel):
    """审计日志筛选参数."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    user_id: Optional[str] = None
    action: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    result: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None