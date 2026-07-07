"""Agent and AgentHeartbeat models."""

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.types import UUID, INET, JSONB

from app.models.base import Base, SoftDeleteMixin, TimestampMixin


class Agent(Base, TimestampMixin, SoftDeleteMixin):
    """Agent (被管主机) 表."""

    __tablename__ = "agents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    agent_id: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True, comment="Agent标识"
    )
    credential: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True, comment="Agent认证凭据"
    )
    hostname: Mapped[str] = mapped_column(
        String(256), nullable=False, comment="主机名"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET, nullable=True, comment="IP地址"
    )
    os_version: Mapped[str] = mapped_column(
        String(64), nullable=False, comment="麒麟OS版本"
    )
    kernel_version: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, comment="内核版本"
    )
    agent_version: Mapped[str] = mapped_column(
        String(32), nullable=False, comment="Agent版本号"
    )
    cpu_cores: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="CPU核心数"
    )
    total_memory: Mapped[int] = mapped_column(
        BigInteger, nullable=False, comment="总内存(MB)"
    )
    disk_total: Mapped[Optional[int]] = mapped_column(
        BigInteger, nullable=True, comment="总磁盘(GB)"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="offline", server_default="offline",
        index=True, comment="状态: online/offline/error/upgrading"
    )
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="最后心跳时间"
    )
    last_heartbeat_ip: Mapped[Optional[str]] = mapped_column(
        INET, nullable=True, comment="最后心跳来源IP"
    )
    registered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="注册时间"
    )
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        comment="首次发现时间"
    )
    tags: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]", comment="标签数组"
    )
    metadata_: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}", comment="扩展元数据"
    )
    config_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", comment="当前配置版本号"
    )

    def __repr__(self):
        return f"<Agent {self.agent_id}>"


class AgentHeartbeat(Base):
    """Agent心跳流水表."""

    __tablename__ = "agent_heartbeats"

    id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, autoincrement=True
    )
    agent_id: Mapped[str] = mapped_column(
        String(128), nullable=False, index=True, comment="Agent标识"
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
        index=True, comment="接收时间"
    )
    cpu_usage: Mapped[Optional[float]] = mapped_column(
        comment="CPU使用率(%)"
    )
    cpu_cores: Mapped[Optional[int]] = mapped_column(
        SmallInteger, nullable=True, comment="CPU核心数"
    )
    memory_total: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="总内存(MB)"
    )
    memory_used: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="已用内存(MB)"
    )
    memory_percent: Mapped[Optional[float]] = mapped_column(
        comment="内存使用率(%)"
    )
    disk_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONB, nullable=True, comment="磁盘信息"
    )
    processes_total: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="总进程数"
    )
    processes_running: Mapped[Optional[int]] = mapped_column(
        Integer, nullable=True, comment="运行中进程数"
    )
    agent_version: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, comment="Agent版本"
    )
    payload: Mapped[Dict[str, Any]] = mapped_column(
        JSONB, nullable=False, comment="原始上报数据"
    )
    ip_address: Mapped[Optional[str]] = mapped_column(
        INET, nullable=True, comment="来源IP"
    )
