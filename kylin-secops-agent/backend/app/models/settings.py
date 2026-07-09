"""SystemSettings model — single-row key-value configuration."""

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SystemSetting(Base):
    """系统设置 — single-row table."""

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True
    )
    mfa_enforced_roles: Mapped[str] = mapped_column(
        Text, default="[]", comment="MFA强制角色列表JSON"
    )
    password_min_length: Mapped[int] = mapped_column(
        Integer, default=12, server_default="12"
    )
    password_expire_days: Mapped[int] = mapped_column(
        Integer, default=90, server_default="90"
    )
    session_timeout_minutes: Mapped[int] = mapped_column(
        Integer, default=60, server_default="60"
    )
    alert_auto_resolve_hours: Mapped[int] = mapped_column(
        Integer, default=72, server_default="72"
    )
    heartbeat_timeout_seconds: Mapped[int] = mapped_column(
        Integer, default=30, server_default="30"
    )
    max_login_attempts: Mapped[int] = mapped_column(
        Integer, default=5, server_default="5"
    )
    lockout_duration_minutes: Mapped[int] = mapped_column(
        Integer, default=15, server_default="15"
    )
    ai_auto_analysis: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1"
    )
    notification_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="1"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(),
        comment="更新时间"
    )
