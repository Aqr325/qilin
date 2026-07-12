"""Policy management routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_pagination
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.schemas.common import ApiResponse, Page
from app.schemas.policy import (
    DeployStatusMap,
    PolicyCreate,
    PolicyDeployRequest,
    PolicyDetail,
    PolicyPreviewTargets,
    PolicyPreviewTargetsRequest,
    PolicyRollbackRequest,
    PolicySummary,
    PolicyToggleRequest,
    PolicyUpdate,
    PolicyValidateRequest,
    PolicyValidationResult,
    PolicyVersion,
)
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["策略管理"])


@router.post("", response_model=ApiResponse[PolicyDetail], status_code=201)
async def create_policy(
    req: PolicyCreate,
    current_user: dict = Depends(require_permission(Permission.POLICY_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """创建策略."""
    result = await policy_service.create_policy(db, req, operator=current_user)
    return ApiResponse(data=result, message="策略创建成功")


@router.get("", response_model=ApiResponse[Page[PolicySummary]])
async def list_policies(
    page: dict = Depends(get_pagination),
    status: str = Query(None),
    policy_type: str = Query(None),
    keyword: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """策略列表."""
    result = await policy_service.list_policies(
        db, page=page["page"], size=page["size"],
        status=status, policy_type=policy_type, keyword=keyword,
    )
    return ApiResponse(data=result)


@router.get("/{policy_id}", response_model=ApiResponse[PolicyDetail])
async def get_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """策略详情."""
    result = await policy_service.get_policy_detail(db, policy_id)
    return ApiResponse(data=result)


@router.put("/{policy_id}", response_model=ApiResponse[PolicyDetail])
async def update_policy(
    policy_id: str,
    req: PolicyUpdate,
    current_user: dict = Depends(require_permission(Permission.POLICY_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """更新策略（创建新版本）."""
    result = await policy_service.update_policy(db, policy_id, req, operator=current_user)
    return ApiResponse(data=result)


@router.delete("/{policy_id}", response_model=ApiResponse)
async def delete_policy(
    policy_id: str,
    current_user: dict = Depends(require_permission(Permission.POLICY_DELETE)),
    db: AsyncSession = Depends(get_db),
):
    """删除策略（软删除）."""
    await policy_service.delete_policy(db, policy_id, operator=current_user)
    return ApiResponse(message="策略已删除")


@router.post("/{policy_id}/deploy", response_model=ApiResponse)
async def deploy_policy(
    policy_id: str,
    req: PolicyDeployRequest,
    current_user: dict = Depends(require_permission(Permission.POLICY_DEPLOY)),
    db: AsyncSession = Depends(get_db),
):
    """下发策略到目标Agent."""
    result = await policy_service.deploy_policy(
        db, policy_id, req.agent_ids, req.force, operator=current_user,
    )
    return ApiResponse(data=result)


@router.post("/{policy_id}/toggle", response_model=ApiResponse[PolicyDetail])
async def toggle_policy(
    policy_id: str,
    req: PolicyToggleRequest,
    current_user: dict = Depends(require_permission(Permission.POLICY_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """切换策略启用/禁用."""
    result = await policy_service.toggle_policy(db, policy_id, req.enabled, operator=current_user)
    return ApiResponse(data=result)


@router.put("/{policy_id}/versions", response_model=ApiResponse[PolicyDetail])
async def rollback_policy(
    policy_id: str,
    req: PolicyRollbackRequest,
    current_user: dict = Depends(require_permission(Permission.POLICY_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """回滚到指定版本."""
    result = await policy_service.rollback_policy(
        db, policy_id, req.version_number, operator=current_user,
    )
    return ApiResponse(data=result)


@router.get("/{policy_id}/versions", response_model=ApiResponse[list[PolicyVersion]])
async def get_policy_versions(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """策略版本历史."""
    result = await policy_service.get_versions(db, policy_id)
    return ApiResponse(data=result)


@router.get("/{policy_id}/deploy-status", response_model=ApiResponse[DeployStatusMap])
async def get_deploy_status(
    policy_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """策略下发状态追踪."""
    result = await policy_service.get_deploy_status(db, policy_id)
    return ApiResponse(data=result)


@router.post("/validate", response_model=ApiResponse[PolicyValidationResult])
async def validate_policy(
    req: PolicyValidateRequest,
    current_user: dict = Depends(get_current_user),
):
    """策略规则语法校验."""
    result = await policy_service.validate_policy(req.rules)
    return ApiResponse(data=result)


@router.post("/preview-targets", response_model=ApiResponse[PolicyPreviewTargets])
async def preview_targets(
    req: PolicyPreviewTargetsRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """预览策略目标Agent范围."""
    result = await policy_service.preview_targets(db, req.target_expression)
    return ApiResponse(data=result)