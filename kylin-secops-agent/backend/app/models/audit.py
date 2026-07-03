"""AuditLog and LoginLog models."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.types import UUID, INET, JSONB

from app.models.base import Base


class LoginLog(Base):
    """登录日志表."""

    __tablename__ = "login_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="日志ID",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True,
        comment="用户ID"
    )
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True, comment="登录用户名"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, comment="状态: success/failed/locked/mfa_required"
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="失败原因"
    )
    ip_address: Mapped[str] = mapped_column(
        INET, nullable=False, index=True, comment="登录IP"
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="客户端UA"
    )
    session_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="会话ID"
    )
    auth_method: Mapped[str] = mapped_column(
        String(32), default="password", server_default="password",
        comment="认证方式"
    )
    login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="登录时间"
    )


class AuditLog(Base):
    """操作审计日志表."""

    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
        comment="审计ID",
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True,
        comment="操作人ID"
    )
    username: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="操作人用户名"
    )
    action: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="操作类型: create/update/delete/action/login/export"
    )
    resource_type: Mapped[str] = mapped_column(
        String(64), nullable=False, index=True,
        comment="资源类型: alert/policy/agent/user/role/system"
    )
    resource_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="资源ID"
    )
    resource_name: Mapped[Optional[str]] = mapped_column(
        String(256), nullable=True, comment="资源名称"
    )
    detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=dict, server_default="{}", comment="操作详情"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET, nullable=True, comment="操作来源IP"
    )
    user_agent: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="客户端UA"
    )
    duration_ms: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="操作耗时(ms)"
    )
    result: Mapped[str] = mapped_column(
        String(16), default="success", server_default="success",
        comment="结果: success/failure/partial"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="错误信息"
    )
    correlation_id: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="关联追踪ID"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        index=True, comment="创建时间"
    )