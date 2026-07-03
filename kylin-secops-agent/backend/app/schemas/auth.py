"""Auth schemas: login, token, profile."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Request ──

class LoginRequest(BaseModel):
    """登录请求."""

    username: str = Field(..., min_length=1, max_length=64, description="用户名")
    password: str = Field(..., min_length=1, max_length=128, description="密码")
    mfa_code: Optional[str] = Field(None, max_length=10, description="MFA验证码")


class RefreshTokenRequest(BaseModel):
    """刷新Token请求."""

    refresh_token: str = Field(..., description="刷新令牌")


class ChangePasswordRequest(BaseModel):
    """修改密码请求."""

    old_password: str = Field(..., min_length=1, max_length=128, description="旧密码")
    new_password: str = Field(
        ..., min_length=12, max_length=128, description="新密码"
    )


# ── Response ──

class TokenPair(BaseModel):
    """Token对."""

    access_token: str = Field(..., description="访问令牌")
    refresh_token: str = Field(..., description="刷新令牌")
    token_type: str = Field(default="bearer")
    expires_in: int = Field(default=900, description="过期时间(秒)")
    refresh_expires_in: int = Field(default=86400, description="刷新令牌过期时间(秒)")


class RoleSummary(BaseModel):
    """角色摘要."""

    id: str
    name: str
    display_name: str


class UserProfile(BaseModel):
    """用户个人信息."""

    id: str
    username: str
    display_name: str
    email: str
    phone: Optional[str] = None
    is_active: bool = True
    is_locked: bool = False
    mfa_enabled: bool = False
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    password_changed_at: Optional[datetime] = None
    roles: List[RoleSummary] = Field(default_factory=list)
    permissions: List[str] = Field(default_factory=list)
    created_at: Optional[datetime] = None


class LoginResponse(BaseModel):
    """登录响应."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    user: UserProfile


class PermissionItem(BaseModel):
    """权限项."""

    code: str
    name: str
    module: str
    action: str
    description: Optional[str] = None