"""AI dialog schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request ──

class AIQueryRequest(BaseModel):
    """AI自然语言查询请求."""

    question: str = Field(..., min_length=1, max_length=2000, description="用户问题")
    context_alert_id: Optional[str] = Field(None, description="关联告警ID")
    timezone: Optional[str] = Field(default="Asia/Shanghai")


class AISuggestRequest(BaseModel):
    """AI告警研判建议请求."""

    alert_id: str = Field(..., description="告警ID")


class AIPlaybookRequest(BaseModel):
    """AI处置剧本生成请求."""

    alert_ids: List[str] = Field(..., min_length=1, max_length=20)
    scenario: Optional[str] = None


class AIFeedbackRequest(BaseModel):
    """AI回答反馈请求."""

    conversation_id: str
    message_id: str
    rating: int = Field(..., ge=1, le=5, description="评分 1-5")
    comment: Optional[str] = None


# ── Response ──

class AIQueryResponse(BaseModel):
    """AI查询响应."""

    conversation_id: str
    message_id: str
    answer: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    data_sources: List[Dict[str, Any]] = Field(default_factory=list)
    suggested_actions: List[Dict[str, Any]] = Field(default_factory=list)
    token_usage: int = 0
    processing_time_ms: int = 0


class AISuggestion(BaseModel):
    """AI研判建议."""

    alert_id: str
    verdict: str = Field(..., description="研判结论: confirmed/false_positive/needs_investigation")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    analysis: str
    recommended_actions: List[str] = Field(default_factory=list)
    related_alerts: List[str] = Field(default_factory=list)
    mitre_mapping: Optional[Dict[str, Any]] = None


class PlaybookStep(BaseModel):
    """处置剧本步骤."""

    order: int
    action: str
    description: str
    params: Optional[Dict[str, Any]] = None
    estimated_time_seconds: Optional[int] = None


class AIPlaybookResponse(BaseModel):
    """处置剧本响应."""

    steps: List[PlaybookStep] = Field(default_factory=list)
    summary: Optional[str] = None
    risk_level: Optional[str] = None


class ConversationSummary(BaseModel):
    """对话历史摘要."""

    id: str
    title: Optional[str] = None
    message_count: Optional[int] = None
    last_message: Optional[str] = None
    related_alert_id: Optional[str] = None
    token_usage: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConversationDetail(BaseModel):
    """对话详情."""

    id: str
    title: Optional[str] = None
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    context: Optional[Dict[str, Any]] = None
    related_alert_id: Optional[str] = None
    feedback_score: Optional[int] = None
    token_usage: int = 0
    model_name: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DashboardOverview(BaseModel):
    """Dashboard overview data."""

    total_alerts: int = 0
    active_alerts: int = 0
    critical_alerts: int = 0
    high_alerts: int = 0
    medium_alerts: int = 0
    low_alerts: int = 0
    resolved_alerts: int = 0
    total_agents: int = 0
    online_agents: int = 0
    offline_agents: int = 0
    active_policies: int = 0
    alerts_today: int = 0
    resolved_today: int = 0
    avg_response_time_hours: Optional[float] = None
    alert_trend: Optional[str] = None  # "up", "down", "stable"


class TrendData(BaseModel):
    """Trend chart data."""

    labels: List[str] = Field(default_factory=list)
    datasets: List[Dict[str, Any]] = Field(default_factory=list)


class HeatmapData(BaseModel):
    """Agent health heatmap data."""

    time_slots: List[str] = Field(default_factory=list)
    agents: List[str] = Field(default_factory=list)
    data: List[List[float]] = Field(default_factory=list)


class TopAlertType(BaseModel):
    """Top alert type item."""

    alert_type: str
    alert_type_label: Optional[str] = None
    count: int = 0
    severity: Optional[str] = None
    trend: Optional[str] = None  # "up", "down", "stable"


# ── Model Config ──

class AiModelConfigCreate(BaseModel):
    """创建模型配置请求."""

    name: str = Field(..., min_length=1, max_length=128, description="配置名称")
    provider: str = Field(..., description="提供商: openai/anthropic/ollama/custom")
    model: str = Field(..., min_length=1, max_length=128, description="模型标识")
    api_url: Optional[str] = Field(None, max_length=512, description="API地址")
    api_key: Optional[str] = Field(None, description="API Key")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="温度参数")
    max_tokens: int = Field(default=4096, ge=1, le=128000, description="最大Token数")
    system_prompt: Optional[str] = Field(None, description="系统提示词")


class AiModelConfigUpdate(BaseModel):
    """更新模型配置请求."""

    name: Optional[str] = Field(None, min_length=1, max_length=128)
    provider: Optional[str] = Field(None)
    model: Optional[str] = Field(None, min_length=1, max_length=128)
    api_url: Optional[str] = Field(None, max_length=512)
    api_key: Optional[str] = Field(None)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=128000)
    system_prompt: Optional[str] = Field(None)
    is_active: Optional[bool] = Field(None)
    is_default: Optional[bool] = Field(None)


class AiModelConfig(BaseModel):
    """模型配置响应."""

    id: str
    name: str
    provider: str
    model: str
    api_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt: Optional[str] = None
    is_active: bool = True
    is_default: bool = False
    has_api_key: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None