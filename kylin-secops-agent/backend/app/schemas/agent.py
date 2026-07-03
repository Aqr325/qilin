"""Agent schemas."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Request ──

class HeartbeatRequest(BaseModel):
    """Agent心跳上报请求."""

    agentId: str = Field(..., description="Agent标识")
    timestamp: Optional[str] = None
    cpu: Dict[str, Any] = Field(default_factory=dict)
    memory: Dict[str, Any] = Field(default_factory=dict)
    disk: List[Dict[str, Any]] = Field(default_factory=list)
    processes: Dict[str, Any] = Field(default_factory=dict)
    version: Optional[str] = None
    status: str = Field(default="online")


class AgentRegisterRequest(BaseModel):
    """Agent注册请求."""

    agent_id: str = Field(..., min_length=1, max_length=128)
    hostname: str = Field(..., max_length=256)
    ip_address: str
    os_version: str
    kernel_version: Optional[str] = None
    agent_version: str
    cpu_cores: int
    total_memory: int
    disk_total: Optional[int] = None
    tags: List[str] = Field(default_factory=list)


class AgentBatchEventsRequest(BaseModel):
    """Agent批量事件上报."""

    events: List[Dict[str, Any]] = Field(..., description="事件列表")


class AgentTaskResultRequest(BaseModel):
    """Agent任务结果上报."""

    task_id: str
    status: str = Field(..., pattern="^(success|failure|running)$")
    output: Optional[str] = None


class AgentUpgradeRequest(BaseModel):
    """Agent升级请求."""

    agent_ids: List[str] = Field(..., min_length=1, max_length=100)
    version: str
    package_url: str


# ── Response ──

class HeartbeatResponse(BaseModel):
    """心跳响应."""

    server_time: str
    next_heartbeat_interval: int = 10
    config_version: int = 0
    config_update_required: bool = False
    pending_tasks: List[Dict[str, Any]] = Field(default_factory=list)
    ack_action: str = "continue"


class AgentSummary(BaseModel):
    """Agent列表摘要."""

    id: str
    agent_id: str
    hostname: str
    ip_address: Optional[str] = None
    os_version: str
    agent_version: str
    status: str
    cpu_cores: int
    total_memory: int
    last_heartbeat: Optional[datetime] = None
    tags: Optional[List[str]] = None
    registered_at: Optional[datetime] = None


class AgentDetail(BaseModel):
    """Agent详情."""

    id: str
    agent_id: str
    hostname: str
    ip_address: Optional[str] = None
    os_version: str
    kernel_version: Optional[str] = None
    agent_version: str
    cpu_cores: int
    total_memory: int
    disk_total: Optional[int] = None
    status: str
    last_heartbeat: Optional[datetime] = None
    last_heartbeat_ip: Optional[str] = None
    registered_at: Optional[datetime] = None
    first_seen_at: Optional[datetime] = None
    tags: Optional[List[str]] = None
    config_version: int = 0
    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgentMetrics(BaseModel):
    """Agent实时指标."""

    cpu_usage: Optional[float] = None
    memory_usage: Optional[float] = None
    memory_total: Optional[int] = None
    memory_used: Optional[int] = None
    disk_usage: Optional[List[Dict[str, Any]]] = None
    processes_total: Optional[int] = None
    processes_running: Optional[int] = None
    last_report_at: Optional[datetime] = None


class HeartbeatRecord(BaseModel):
    """心跳记录."""

    id: int
    agent_id: str
    received_at: Optional[datetime] = None
    cpu_usage: Optional[float] = None
    memory_percent: Optional[float] = None
    processes_total: Optional[int] = None
    agent_version: Optional[str] = None


class AgentGlobalStats(BaseModel):
    """Agent全局统计."""

    total: int = 0
    online: int = 0
    offline: int = 0
    error: int = 0
    upgrading: int = 0
    online_rate: float = 0.0
    versions: List[Dict[str, Any]] = Field(default_factory=list)
    os_versions: List[Dict[str, Any]] = Field(default_factory=list)


class AgentTask(BaseModel):
    """Agent任务."""

    task_id: str
    type: str
    status: str
    created_at: Optional[datetime] = None
    params: Optional[Dict[str, Any]] = None


class HealthOverview(BaseModel):
    """健康检查总览."""

    total_agents: int = 0
    online_agents: int = 0
    offline_agents: int = 0
    error_agents: int = 0
    online_rate: float = 0.0
    avg_cpu_usage: Optional[float] = None
    avg_memory_usage: Optional[float] = None
    versions: List[Dict[str, Any]] = Field(default_factory=list)


class UpgradeRecord(BaseModel):
    """升级记录."""

    task_id: str
    agent_id: str
    from_version: str
    to_version: str
    status: str
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class OnlineMapItem(BaseModel):
    """在线分布项."""

    agent_id: str
    hostname: str
    ip_address: Optional[str] = None
    status: str
    last_heartbeat: Optional[datetime] = None
    os_version: Optional[str] = None