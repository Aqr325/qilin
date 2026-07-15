"""AI dialog routes."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_pagination
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.schemas.ai import (
    AIFeedbackRequest,
    AIPlaybookRequest,
    AIPlaybookResponse,
    AIQueryRequest,
    AIQueryResponse,
    AISuggestRequest,
    AISuggestion,
    AiModelTestRequest,
    AiModelTestResponse,
    AiModelConfig,
    AiModelConfigCreate,
    AiModelConfigUpdate,
    ConversationDetail,
    ConversationSummary,
)
from app.schemas.common import ApiResponse, Page
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI对话"])


@router.post("/query", response_model=ApiResponse[AIQueryResponse])
async def ai_query(
    req: AIQueryRequest,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """自然语言运维查询."""
    if req.context_alert_id:
        try:
            uuid.UUID(str(req.context_alert_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="非法的 context_alert_id")
    result = await ai_service.query(db, req, user=current_user)
    return ApiResponse(data=result)


@router.post("/suggest", response_model=ApiResponse[AISuggestion])
async def ai_suggest(
    req: AISuggestRequest,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """AI告警研判建议."""
    result = await ai_service.suggest(db, req.alert_id, user=current_user)
    return ApiResponse(data=result)


@router.post("/playbook", response_model=ApiResponse[AIPlaybookResponse])
async def ai_playbook(
    req: AIPlaybookRequest,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """AI生成处置剧本."""
    result = await ai_service.generate_playbook(
        db, req.alert_ids, req.scenario, user=current_user,
    )
    return ApiResponse(data=result)


@router.get("/conversations", response_model=ApiResponse[Page[ConversationSummary]])
async def list_conversations(
    page: dict = Depends(get_pagination),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI对话历史."""
    result = await ai_service.list_conversations(
        db, user_id=current_user["id"],
        page=page["page"], size=page["size"],
    )
    return ApiResponse(data=result)


@router.get("/conversations/{conv_id}", response_model=ApiResponse[ConversationDetail])
async def get_conversation(
    conv_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对话详情."""
    result = await ai_service.get_conversation(db, conv_id, user=current_user)
    return ApiResponse(data=result)


@router.delete("/conversations/{conv_id}", response_model=ApiResponse)
async def delete_conversation(
    conv_id: uuid.UUID,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """删除对话."""
    await ai_service.delete_conversation(db, conv_id, operator=current_user)
    return ApiResponse(message="对话已删除")


@router.post("/feedback", response_model=ApiResponse)
async def ai_feedback(
    req: AIFeedbackRequest,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """AI回答反馈."""
    await ai_service.save_feedback(db, req, user=current_user)
    return ApiResponse(message="反馈已保存")


# ── Model Config CRUD ──

@router.get("/model-configs", response_model=ApiResponse[list[AiModelConfig]])
async def list_model_configs(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户的模型配置列表."""
    result = await ai_service.list_model_configs(db, user_id=current_user["id"])
    return ApiResponse(data=result)


@router.post("/model-configs", response_model=ApiResponse[AiModelConfig])
async def create_model_config(
    req: AiModelConfigCreate,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """创建模型配置."""
    result = await ai_service.create_model_config(db, req, user_id=current_user["id"])
    return ApiResponse(data=result)


@router.post("/model-configs/test", response_model=ApiResponse[AiModelTestResponse])
async def test_model_config_endpoint(
    req: AiModelTestRequest,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """测试模型连通性（可使用已保存配置或临时参数）."""
    result = await ai_service.test_model_config(db, req, user_id=current_user["id"])
    return ApiResponse(data=result)


@router.get("/model-configs/{config_id}", response_model=ApiResponse[AiModelConfig])
async def get_model_config(
    config_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取单个模型配置."""
    result = await ai_service.get_model_config(db, config_id, user_id=current_user["id"])
    return ApiResponse(data=result)


@router.put("/model-configs/{config_id}", response_model=ApiResponse[AiModelConfig])
async def update_model_config(
    config_id: uuid.UUID,
    req: AiModelConfigUpdate,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """更新模型配置."""
    result = await ai_service.update_model_config(db, config_id, req, user_id=current_user["id"])
    return ApiResponse(data=result)


@router.delete("/model-configs/{config_id}", response_model=ApiResponse)
async def delete_model_config(
    config_id: uuid.UUID,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """删除模型配置."""
    await ai_service.delete_model_config(db, config_id, user_id=current_user["id"])
    return ApiResponse(message="模型配置已删除")


@router.put("/model-configs/{config_id}/set-default", response_model=ApiResponse[AiModelConfig])
async def set_default_model_config(
    config_id: uuid.UUID,
    current_user: dict = Depends(require_permission(Permission.AI_WRITE)),
    db: AsyncSession = Depends(get_db),
):
    """设置默认模型."""
    result = await ai_service.set_default_model_config(db, config_id, user_id=current_user["id"])
    return ApiResponse(data=result)