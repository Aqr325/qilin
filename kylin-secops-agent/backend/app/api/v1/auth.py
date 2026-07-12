"""Auth routes: login, refresh, logout, profile."""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, get_request_id
from app.core.database import get_db
from app.core.security import decode_token
from app.core.token_blacklist import token_blacklist
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    MFAToggleRequest,
    PermissionItem,
    RefreshTokenRequest,
    TokenPair,
    UserProfile,
    UserProfileUpdateRequest,
)
from app.schemas.common import ApiResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login", response_model=ApiResponse[LoginResponse])
async def login(
    request: Request,
    req: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """用户登录."""
    result = await auth_service.login(
        db, req.username, req.password, req.mfa_code,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return ApiResponse(data=result)


@router.post("/refresh", response_model=ApiResponse[TokenPair])
async def refresh_token(
    req: RefreshTokenRequest,
    db: AsyncSession = Depends(get_db),
):
    """刷新Token."""
    result = await auth_service.refresh_token(db, req.refresh_token)
    return ApiResponse(data=result)


@router.post("/logout", response_model=ApiResponse)
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    refresh_token: Optional[str] = Body(None, embed=True),
):
    """退出登录并立即吊销当前访问令牌（及可选的刷新令牌）."""
    await auth_service.logout(current_user)

    # Revoke the access token (from the Authorization header) and, if the
    # client also supplies its refresh token, that one too — so a stolen
    # refresh token cannot mint new tokens after logout.
    authorization = request.headers.get("authorization")
    tokens_to_revoke = []
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() == "bearer" and token:
            tokens_to_revoke.append(token)
    if refresh_token:
        tokens_to_revoke.append(refresh_token)

    for tok in tokens_to_revoke:
        try:
            payload = decode_token(tok)
            jti = payload.get("jti")
            if jti:
                exp = payload.get("exp")
                exp_dt = (
                    datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
                )
                token_blacklist.blacklist(jti, exp_dt)
        except Exception:
            # If decoding fails, there is nothing to revoke; ignore.
            pass

    return ApiResponse(message="退出成功")


@router.get("/me", response_model=ApiResponse[UserProfile])
async def get_me(
    current_user: dict = Depends(get_current_user),
):
    """获取当前用户信息."""
    return ApiResponse(data=UserProfile(**current_user))


@router.put("/me/password", response_model=ApiResponse)
async def change_password(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改当前用户密码."""
    await auth_service.change_password(
        db, current_user["id"], req.old_password, req.new_password
    )
    return ApiResponse(message="密码修改成功")


@router.get("/me/permissions", response_model=ApiResponse[list[PermissionItem]])
async def get_my_permissions(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户权限列表."""
    result = await auth_service.get_user_permissions(db, current_user["id"])
    return ApiResponse(data=result)


@router.post("/change-password", response_model=ApiResponse)
async def change_password_compat(
    req: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """修改密码（兼容前端端点）."""
    await auth_service.change_password(
        db, current_user["id"], req.old_password, req.new_password
    )
    return ApiResponse(message="密码修改成功")


@router.put("/me/profile", response_model=ApiResponse[UserProfile])
async def update_profile(
    req: UserProfileUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户资料."""
    updated = await auth_service.update_user_profile(
        db, current_user["id"],
        display_name=req.display_name,
        email=req.email,
        phone=req.phone,
    )
    return ApiResponse(data=UserProfile(**updated))


@router.put("/mfa", response_model=ApiResponse[UserProfile])
async def toggle_mfa(
    req: MFAToggleRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """切换MFA开关."""
    updated = await auth_service.toggle_mfa(db, current_user["id"], req.enabled)
    return ApiResponse(data=UserProfile(**updated))