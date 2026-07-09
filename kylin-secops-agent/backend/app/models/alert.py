"""Alert and AlertStatusHistory models."""

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


class Alert(Base, TimestampMixin, SoftDeleteMixin):
    """告警表."""

    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    alert_seq: Mapped[int] = mapped_column(
        BigInteger, autoincrement=True, nullable=False, comment="告警序号"
    )
    agent_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="关联Agent标识"
    )
    alert_type: Mapped[str] = mapped_column(
        String(32), nullable=False, index=True, comment="告警类型"
    )
    severity: Mapped[str] = mapped_column(
        String(16), nullable=False, index=True,
        comment="严重度: critical/high/medium/low/info"
    )
    title: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="告警标题"
    )
    description: Mapped[str] = mapped_column(
        Text, nullable=False, comment="告警描述"
    )
    detail: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=dict, server_default="{}", comment="告警详细数据"
    )
    source: Mapped[str] = mapped_column(
        String(32), nullable=False, default="agent", server_default="agent",
        comment="来源: agent/system/manual"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="new", server_default="new",
        index=True, comment="状态"
    )
    status_changed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="最后状态变更时间"
    )
    mitre_technique_id: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, index=True, comment="MITRE ATT&CK技术ID"
    )
    mitre_tactic: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="MITRE ATT&CK战术"
    )
    mitre_technique_name: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="MITRE技术名称"
    )
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True,
        comment="处理人"
    )
    assigned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="指派时间"
    )
    suppressed: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="FALSE", comment="是否被抑制"
    )
    suppressed_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="抑制到期时间"
    )
    suppress_reason: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="抑制原因"
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="解决时间"
    )
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="解决人"
    )
    correlation_key: Mapped[Optional[str]] = mapped_column(
        String(128), nullable=True, comment="关联聚合键"
    )
    correlation_count: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="聚合告警计数"
    )
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="首次检测时间"
    )
    last_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, comment="最后检测时间"
    )
    alert_count: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1", comment="告警聚合次数"
    )
    source_ip: Mapped[Optional[str]] = mapped_column(
        String(45), nullable=True, comment="来源IP地址"
    )

    def __repr__(self):
        return f"<Alert {self.alert_seq}: {self.title[:40]}>"


class AlertStatusHistory(Base):
    """告警状态流转历史表."""

    __tablename__ = "alert_status_history"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    alert_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("alerts.id", ondelete="CASCADE"),
        nullable=False, index=True, comment="告警ID"
    )
    from_status: Mapped[Optional[str]] = mapped_column(
        String(20), nullable=True, comment="原状态"
    )
    to_status: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="新状态"
    )
    operator_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, comment="操作人"
    )
    operator_name: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="操作人名称"
    )
    operation: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="操作类型"
    )
    comment: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="备注"
    )
    source: Mapped[str] = mapped_column(
        String(16), default="manual", server_default="manual",
        comment="来源: manual/auto/ai"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )