"""Policy, PolicyVersion, PolicyTarget models."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.types import UUID, JSONB

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Policy(Base, TimestampMixin, SoftDeleteMixin):
    """策略表."""

    __tablename__ = "policies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="策略名称"
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="策略描述"
    )
    policy_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="策略类型"
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="当前版本号"
    )
    rules: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="策略规则集"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="draft", server_default="draft",
        index=True, comment="状态: draft/enabled/disabled/archived"
    )
    target_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default="all", server_default="all",
        comment="目标类型: all/tags/agent_ids/expression"
    )
    target_value: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]", comment="目标值"
    )
    priority: Mapped[int] = mapped_column(
        Integer, default=100, server_default="100", comment="策略优先级"
    )
    effective_start: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="生效开始时间"
    )
    effective_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="生效结束时间"
    )
    is_template: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="0", comment="是否模板"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True,
        comment="创建人"
    )
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="最后修改人"
    )
    deployed_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="已下发版本号"
    )
    last_deployed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后下发时间"
    )


class PolicyVersion(Base):
    """策略版本表."""

    __tablename__ = "policy_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False, comment="策略ID"
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="版本号"
    )
    rules: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="该版本的规则集"
    )
    changelog: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="变更说明"
    )
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="创建人"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class PolicyTarget(Base):
    """策略目标Agent表."""

    __tablename__ = "policy_targets"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("policies.id", ondelete="CASCADE"),
        nullable=False, comment="策略ID"
    )
    agent_id: Mapped[str] = mapped_column(
        String(128), nullable=False, comment="Agent标识"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending",
        index=True, comment="下发状态: pending/deployed/failed"
    )
    deployed_version: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="实际下发版本号"
    )
    deployed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="下发时间"
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="失败原因"
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="重试次数"
    )