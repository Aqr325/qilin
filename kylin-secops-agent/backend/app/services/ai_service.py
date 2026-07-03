"""AI service: natural language query, alert analysis, playbook generation."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import AiConversation
from app.schemas.ai import (
    AIFeedbackRequest,
    AIPlaybookResponse,
    AIQueryRequest,
    AIQueryResponse,
    AISuggestion,
    ConversationDetail,
    ConversationSummary,
    PlaybookStep,
)
from app.schemas.common import Page


async def query(
    db: AsyncSession,
    req: AIQueryRequest,
    user: dict,
) -> AIQueryResponse:
    """Process natural language query."""
    conv_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())

    # Mock AI response for now
    answer = (
        f"正在查询: {req.question}\n\n"
        f"根据数据分析，暂未发现异常。"
    )

    # Save conversation
    conv = AiConversation(
        id=uuid.UUID(conv_id),
        user_id=uuid.UUID(user["id"]),
        title=req.question[:100],
        messages=[
            {"role": "user", "content": req.question, "id": msg_id},
            {"role": "assistant", "content": answer, "id": str(uuid.uuid4())},
        ],
        context={"timezone": req.timezone or "Asia/Shanghai"},
        model_name="qwen2.5-7b",
        token_usage=150,
    )
    if req.context_alert_id:
        conv.related_alert_id = uuid.UUID(req.context_alert_id)
    db.add(conv)
    await db.flush()

    return AIQueryResponse(
        conversation_id=conv_id,
        message_id=msg_id,
        answer=answer,
        confidence=0.95,
        data_sources=[],
        suggested_actions=[],
        token_usage=150,
        processing_time_ms=500,
    )


async def suggest(
    db: AsyncSession,
    alert_id: str,
    user: dict,
) -> AISuggestion:
    """Generate AI analysis suggestion for an alert."""
    return AISuggestion(
        alert_id=alert_id,
        verdict="needs_investigation",
        confidence=0.7,
        analysis="AI研判分析：该告警需要进一步调查。建议检查Agent日志和关联事件。",
        recommended_actions=[
            "检查Agent系统日志",
            "查看关联告警",
            "确认是否存在误报可能",
        ],
        related_alerts=[],
        mitre_mapping=None,
    )


async def generate_playbook(
    db: AsyncSession,
    alert_ids: List[str],
    scenario: Optional[str],
    user: dict,
) -> AIPlaybookResponse:
    """Generate incident response playbook."""
    return AIPlaybookResponse(
        steps=[
            PlaybookStep(
                order=1,
                action="分析告警详情",
                description=f"查看 {len(alert_ids)} 条告警的详细信息和关联事件",
                estimated_time_seconds=120,
            ),
            PlaybookStep(
                order=2,
                action="确认影响范围",
                description="确定受影响的Agent和系统",
                estimated_time_seconds=300,
            ),
            PlaybookStep(
                order=3,
                action="执行处置",
                description="根据告警类型执行相应处置动作",
                estimated_time_seconds=600,
            ),
            PlaybookStep(
                order=4,
                action="更新告警状态",
                description="将告警状态更新为已解决并添加处置备注",
                estimated_time_seconds=60,
            ),
        ],
        summary="标准告警处置流程",
        risk_level="medium",
    )


async def list_conversations(
    db: AsyncSession,
    user_id: str,
    page: int = 1,
    size: int = 20,
) -> Page[ConversationSummary]:
    """List AI conversation history."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import desc, select, func

    repo = BaseRepository(AiConversation, db)
    query = select(AiConversation).where(AiConversation.user_id == uuid.UUID(user_id))

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    query = query.order_by(desc(AiConversation.updated_at)).offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    convs = result.scalars().all()

    items = [
        ConversationSummary(
            id=str(c.id),
            title=c.title,
            message_count=len(c.messages) if c.messages else 0,
            last_message=c.messages[-1].get("content", "")[:100] if c.messages else None,
            related_alert_id=str(c.related_alert_id) if c.related_alert_id else None,
            token_usage=c.token_usage,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in convs
    ]
    return Page.create(items, total, page, size)


async def get_conversation(
    db: AsyncSession,
    conv_id: str,
    user: dict,
) -> ConversationDetail:
    """Get conversation detail."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import select

    repo = BaseRepository(AiConversation, db)
    result = await db.execute(
        select(AiConversation).where(AiConversation.id == uuid.UUID(conv_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    return ConversationDetail(
        id=str(conv.id),
        title=conv.title,
        messages=conv.messages or [],
        context=conv.context,
        related_alert_id=str(conv.related_alert_id) if conv.related_alert_id else None,
        feedback_score=conv.feedback_score,
        token_usage=conv.token_usage,
        model_name=conv.model_name,
        duration_ms=conv.duration_ms,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


async def delete_conversation(db: AsyncSession, conv_id: str, operator: dict):
    """Delete a conversation."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import select

    repo = BaseRepository(AiConversation, db)
    result = await db.execute(
        select(AiConversation).where(AiConversation.id == uuid.UUID(conv_id))
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")
    await db.delete(conv)
    await db.flush()


async def save_feedback(
    db: AsyncSession,
    req: AIFeedbackRequest,
    user: dict,
):
    """Save feedback for AI response."""
    from app.repositories.base import BaseRepository
    from sqlalchemy import select

    result = await db.execute(
        select(AiConversation).where(
            AiConversation.id == uuid.UUID(req.conversation_id),
            AiConversation.user_id == uuid.UUID(user["id"]),
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="对话不存在")

    conv.feedback_score = req.rating
    conv.feedback_comment = req.comment
    await db.flush()