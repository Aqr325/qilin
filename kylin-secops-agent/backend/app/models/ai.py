"""AiConversation model."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.types import UUID, JSONB

from app.models.base import Base, TimestampMixin


class AiConversation(Base, TimestampMixin):
    """AI对话记录表."""

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
        comment="用户ID"
    )
    title: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, comment="对话标题"
    )
    messages: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]",
        comment="消息数组"
    )
    context: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=dict, server_default="{}", comment="上下文数据"
    )
    related_alert_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id"), nullable=True,
        comment="关联告警"
    )
    feedback_score: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True, comment="用户反馈评分 (1-5)"
    )
    feedback_comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="反馈评论"
    )
    token_usage: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="Token消耗"
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="AI模型名称"
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="处理耗时"
    )