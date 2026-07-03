"""Auth routes: login, refresh, logout, profile."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_optional, get_request_id
from app.core.database import get_db
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    PermissionItem,
    RefreshTokenRequest,
    TokenPair,
    UserProfile,
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
):
    """退出登录."""
    await auth_service.logout(current_user)
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