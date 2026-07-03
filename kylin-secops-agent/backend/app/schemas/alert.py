"""Alert schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request ──

class UpdateAlertStatusRequest(BaseModel):
    """更新告警状态请求."""

    status: str = Field(..., description="目标状态")
    comment: Optional[str] = None


class BatchStatusRequest(BaseModel):
    """批量处置告警请求."""

    alert_ids: List[str] = Field(..., min_length=1, max_length=100)
    status: str = Field(..., description="目标状态")
    comment: Optional[str] = None
    notify_assignee: bool = False


class AssignAlertRequest(BaseModel):
    """指派告警请求."""

    assignee_id: str = Field(..., description="处理人ID")


class SuppressAlertRequest(BaseModel):
    """添加告警抑制规则请求."""

    rule_config: Dict[str, Any]
    expire_time: Optional[datetime] = None


# ── Response ──

class AlertSummary(BaseModel):
    """告警列表摘要."""

    id: str
    alert_seq: int
    agent_id: str
    hostname: Optional[str] = None
    alert_type: str
    alert_type_label: Optional[str] = None
    severity: str
    severity_label: Optional[str] = None
    title: str
    description: str
    status: str
    status_label: Optional[str] = None
    mitre_technique_id: Optional[str] = None
    mitre_tactic: Optional[str] = None
    mitre_technique_name: Optional[str] = None
    assignee_name: Optional[str] = None
    assigned_at: Optional[datetime] = None
    suppressed: bool = False
    correlation_count: int = 1
    first_detected_at: Optional[datetime] = None
    last_detected_at: Optional[datetime] = None
    alert_count: int = 1
    source_ip: Optional[str] = None
    created_at: Optional[datetime] = None


class AlertDetail(BaseModel):
    """告警详情."""

    id: str
    alert_seq: int
    agent_id: str
    hostname: Optional[str] = None
    alert_type: str
    alert_type_label: Optional[str] = None
    severity: str
    severity_label: Optional[str] = None
    title: str
    description: str
    detail: Optional[Dict[str, Any]] = None
    source: str
    status: str
    status_label: Optional[str] = None
    status_changed_at: Optional[datetime] = None
    mitre_technique_id: Optional[str] = None
    mitre_tactic: Optional[str] = None
    mitre_technique_name: Optional[str] = None
    assignee: Optional[Dict[str, Any]] = None
    assigned_at: Optional[datetime] = None
    suppressed: bool = False
    suppressed_until: Optional[datetime] = None
    suppress_reason: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolved_by_name: Optional[str] = None
    correlation_key: Optional[str] = None
    correlation_count: int = 1
    first_detected_at: Optional[datetime] = None
    last_detected_at: Optional[datetime] = None
    alert_count: int = 1
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    source_ip: Optional[str] = None


class AlertStats(BaseModel):
    """告警统计概览."""

    total: int = 0
    by_severity: Dict[str, int] = Field(default_factory=dict)
    by_status: Dict[str, int] = Field(default_factory=dict)
    by_type: Dict[str, int] = Field(default_factory=dict)
    new_count: int = 0
    critical_count: int = 0
    resolved_count: int = 0
    avg_resolve_time_hours: Optional[float] = None


class AlertStatusChange(BaseModel):
    """告警状态变更记录."""

    id: int
    from_status: Optional[str] = None
    to_status: str
    operator_name: Optional[str] = None
    operation: str
    comment: Optional[str] = None
    source: str
    created_at: Optional[datetime] = None


class BatchStatusResult(BaseModel):
    """批量处置结果."""

    total: int = 0
    processed: int = 0
    failed: int = 0
    details: List[Dict[str, Any]] = Field(default_factory=list)


class SuppressRule(BaseModel):
    """抑制规则."""

    id: str
    alert_id: str
    rule_config: Dict[str, Any]
    expire_time: Optional[datetime] = None
    created_at: Optional[datetime] = None


class MitreMatrixItem(BaseModel):
    """MITRE矩阵项."""

    tactic_id: str
    tactic_name: str
    techniques: List[Dict[str, Any]] = Field(default_factory=list)


class TimelineData(BaseModel):
    """告警时间线数据."""

    timestamps: List[str] = Field(default_factory=list)
    series: List[Dict[str, Any]] = Field(default_factory=list)


class AlertFilterParams(BaseModel):
    """告警筛选参数."""

    page: int = Field(default=1, ge=1)
    size: int = Field(default=20, ge=1, le=100)
    status: Optional[str] = None
    severity: Optional[str] = None
    alert_type: Optional[str] = None
    agent_id: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    mitre_technique: Optional[str] = None
    keyword: Optional[str] = None
    assignee_id: Optional[str] = None
    sort_by: Optional[str] = "created_at"
    sort_order: Optional[str] = "desc"