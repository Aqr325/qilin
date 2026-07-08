"""AI conversation and model configuration models."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.models.types import UUID, JSONB

from app.models.base import Base, TimestampMixin


class AiConversation(Base, TimestampMixin):
    """AI对话记录表."""

    __tablename__ = "ai_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
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


class AiModelConfig(Base, TimestampMixin):
    """自定义大模型配置表."""

    __tablename__ = "ai_model_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
        comment="配置所属用户"
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="配置名称，如：GPT-4-turbo"
    )
    provider: Mapped[str] = mapped_column(
        String(64), nullable=False, default="custom",
        comment="提供商：openai / anthropic / ollama / custom"
    )
    model: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="模型标识，如：gpt-4-turbo"
    )
    api_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True, comment="API 地址（可选）"
    )
    api_key: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="API Key"
    )
    temperature: Mapped[float] = mapped_column(
        Float, default=0.7, server_default="0.7", comment="温度参数 0.0-2.0"
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, default=4096, server_default="4096", comment="最大输出 Token 数"
    )
    system_prompt: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="系统提示词（可选）"
    )
    is_active: Mapped[bool] = mapped_column(
        SmallInteger, default=1, server_default="1", comment="是否启用"
    )
    is_default: Mapped[bool] = mapped_column(
        SmallInteger, default=0, server_default="0", comment="是否为默认模型"
    )

    @validates('api_key')
    def validate_api_key(self, key, value):
        if value and not value.startswith('gAAAAA'):
            from app.core.security import encrypt_api_key
            return encrypt_api_key(value)
        return value