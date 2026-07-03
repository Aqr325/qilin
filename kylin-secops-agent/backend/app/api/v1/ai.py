"""AI dialog routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_pagination
from app.core.database import get_db
from app.schemas.ai import (
    AIFeedbackRequest,
    AIPlaybookRequest,
    AIPlaybookResponse,
    AIQueryRequest,
    AIQueryResponse,
    AISuggestRequest,
    AISuggestion,
    ConversationDetail,
    ConversationSummary,
)
from app.schemas.common import ApiResponse, Page
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["AI对话"])


@router.post("/query", response_model=ApiResponse[AIQueryResponse])
async def ai_query(
    req: AIQueryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自然语言运维查询."""
    result = await ai_service.query(db, req, user=current_user)
    return ApiResponse(data=result)


@router.post("/suggest", response_model=ApiResponse[AISuggestion])
async def ai_suggest(
    req: AISuggestRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI告警研判建议."""
    result = await ai_service.suggest(db, req.alert_id, user=current_user)
    return ApiResponse(data=result)


@router.post("/playbook", response_model=ApiResponse[AIPlaybookResponse])
async def ai_playbook(
    req: AIPlaybookRequest,
    current_user: dict = Depends(get_current_user),
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
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """对话详情."""
    result = await ai_service.get_conversation(db, conv_id, user=current_user)
    return ApiResponse(data=result)


@router.delete("/conversations/{conv_id}", response_model=ApiResponse)
async def delete_conversation(
    conv_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除对话."""
    await ai_service.delete_conversation(db, conv_id, operator=current_user)
    return ApiResponse(message="对话已删除")


@router.post("/feedback", response_model=ApiResponse)
async def ai_feedback(
    req: AIFeedbackRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI回答反馈."""
    await ai_service.save_feedback(db, req, user=current_user)
    return ApiResponse(message="反馈已保存")