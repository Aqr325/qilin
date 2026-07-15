"""Agent management routes (both management and communication)."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

import hmac

from app.api.deps import get_current_user, get_pagination, get_request_id
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.models.agent import Agent
from app.schemas.agent import (
    AgentBatchEventsRequest,
    AgentBatchRestartRequest,
    AgentDetail,
    AgentGlobalStats,
    AgentHealthScore,
    AgentMetrics,
    AgentRegisterRequest,
    AgentSummary,
    AgentTask,
    AgentTaskResultRequest,
    AgentUpgradeRequest,
    HealthOverview,
    HeartbeatRecord,
    HeartbeatRequest,
    HeartbeatResponse,
    OnlineMapItem,
    UpgradeRecord,
)
from app.schemas.common import ApiResponse, Page
from app.services import agent_service

router = APIRouter(prefix="/agent", tags=["Agent通信"])


async def validate_agent_token(
    x_agent_token: str = Header(None, alias="X-Agent-Token"),
    db: AsyncSession = Depends(get_db),
):
    """验证Agent通信令牌。"""
    if not x_agent_token:
        raise HTTPException(status_code=401, detail="Missing X-Agent-Token header")
    from sqlalchemy import select
    from app.models.agent import Agent
    result = await db.execute(
        select(Agent).where(Agent.credential == x_agent_token).where(Agent.is_deleted == False)
    )
    agent = result.scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=401, detail="Invalid agent token")
    return agent


@router.post("/heartbeat", response_model=ApiResponse[HeartbeatResponse])
async def agent_heartbeat(
    req: HeartbeatRequest,
    request: Request,
    agent: Agent = Depends(validate_agent_token),
    db: AsyncSession = Depends(get_db),
):
    """Agent心跳上报."""
    result = await agent_service.process_heartbeat(
        db, req, ip_address=request.client.host if request.client else None
    )
    return ApiResponse(data=result)


@router.post("/register", response_model=ApiResponse)
async def agent_register(
    req: AgentRegisterRequest,
    x_bootstrap_token: str = Header(None, alias="X-Agent-Bootstrap-Token"),
    db: AsyncSession = Depends(get_db),
):
    """Agent注册（需 bootstrap token，防止未授权写入数据库）."""
    expected = settings.AGENT_BOOTSTRAP_TOKEN
    if not expected:
        raise HTTPException(
            status_code=403,
            detail="Agent 注册未启用：未配置 AGENT_BOOTSTRAP_TOKEN",
        )
    if not x_bootstrap_token or not hmac.compare_digest(x_bootstrap_token, expected):
        raise HTTPException(status_code=401, detail="缺少或非法的 bootstrap token")
    result = await agent_service.register_agent(db, req)
    return ApiResponse(data=result)


@router.post("/events", response_model=ApiResponse)
async def agent_batch_events(
    req: AgentBatchEventsRequest,
    agent: Agent = Depends(validate_agent_token),
    db: AsyncSession = Depends(get_db),
):
    """Agent批量事件上报."""
    result = await agent_service.process_batch_events(db, req)
    return ApiResponse(data=result)


@router.get("/{agent_id}/config", response_model=ApiResponse)
async def agent_get_config(
    agent_id: str,
    agent: Agent = Depends(validate_agent_token),
    db: AsyncSession = Depends(get_db),
):
    """Agent拉取配置."""
    config = await agent_service.get_agent_config(db, agent_id)
    return ApiResponse(data=config)


@router.post("/{agent_id}/result", response_model=ApiResponse)
async def agent_task_result(
    agent_id: str,
    req: AgentTaskResultRequest,
    agent: Agent = Depends(validate_agent_token),
    db: AsyncSession = Depends(get_db),
):
    """Agent任务结果上报."""
    result = await agent_service.process_task_result(
        db, agent_id, {
            "task_id": req.task_id,
            "status": req.status,
            "output": req.output,
        }
    )
    return ApiResponse(data=result)


# ── Agent Management Routes ──

mgmt_router = APIRouter(prefix="/agents", tags=["Agent管理"])


@mgmt_router.get("", response_model=ApiResponse[Page[AgentSummary]])
async def list_agents(
    page: dict = Depends(get_pagination),
    status: str = Query(None),
    version: str = Query(None, alias="agent_version"),
    keyword: str = Query(None),
    os_version: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent列表（分页+筛选）."""
    result = await agent_service.list_agents(
        db, page=page["page"], size=page["size"],
        status=status, version=version,
        keyword=keyword, os_version=os_version,
    )
    return ApiResponse(data=result)


@mgmt_router.get("/stats", response_model=ApiResponse[AgentGlobalStats])
async def agent_stats(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent全局统计."""
    result = await agent_service.get_global_stats(db)
    return ApiResponse(data=result)


@mgmt_router.get("/health-check", response_model=ApiResponse[HealthOverview])
async def health_check(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent健康检查总览."""
    result = await agent_service.get_health_overview(db)
    return ApiResponse(data=result)


@mgmt_router.get("/online-map", response_model=ApiResponse[list[OnlineMapItem]])
async def online_map(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent在线分布地图."""
    result = await agent_service.get_online_map(db)
    return ApiResponse(data=result)


@mgmt_router.get("/{agent_id}", response_model=ApiResponse[AgentDetail])
async def get_agent(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent详情."""
    result = await agent_service.get_agent_detail(db, agent_id)
    return ApiResponse(data=result)


@mgmt_router.get("/{agent_id}/metrics", response_model=ApiResponse[AgentMetrics])
async def get_agent_metrics(
    agent_id: str,
    time_range: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent实时指标."""
    result = await agent_service.get_agent_metrics(db, agent_id, time_range)
    return ApiResponse(data=result)


@mgmt_router.get("/{agent_id}/heartbeats", response_model=ApiResponse[Page[HeartbeatRecord]])
async def get_agent_heartbeats(
    agent_id: str,
    page: dict = Depends(get_pagination),
    start_time: str = Query(None),
    end_time: str = Query(None),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent心跳历史."""
    result = await agent_service.get_heartbeat_history(
        db, agent_id, page=page["page"], size=page["size"],
        start_time=start_time, end_time=end_time,
    )
    return ApiResponse(data=result)


@mgmt_router.post("/upgrade", response_model=ApiResponse)
async def upgrade_agents(
    req: AgentUpgradeRequest,
    current_user: dict = Depends(require_permission(Permission.AGENT_UPGRADE)),
    db: AsyncSession = Depends(get_db),
):
    """远程升级Agent."""
    result = await agent_service.upgrade_agents(db, req, operator=current_user["username"])
    return ApiResponse(data=result)


@mgmt_router.get("/{agent_id}/upgrade-history", response_model=ApiResponse[list[UpgradeRecord]])
async def get_upgrade_history(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent升级历史."""
    result = await agent_service.get_upgrade_history(db, agent_id)
    return ApiResponse(data=result)


@mgmt_router.get("/{agent_id}/health-score", response_model=ApiResponse[AgentHealthScore])
async def get_agent_health_score(
    agent_id: str,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent健康评分详情（实时计算）。"""
    result = await agent_service.get_agent_health_score(db, agent_id)
    return ApiResponse(data=result)


@mgmt_router.post("/batch-restart", response_model=ApiResponse)
async def batch_restart_agents(
    req: AgentBatchRestartRequest,
    current_user: dict = Depends(require_permission(Permission.AGENT_RESTART)),
    db: AsyncSession = Depends(get_db),
):
    """批量重启Agent（复用 restart_agent 逻辑）。"""
    result = await agent_service.batch_restart_agents(
        db, req.agent_ids, operator=current_user["username"]
    )
    return ApiResponse(data=result)


@mgmt_router.post("/{agent_id}/restart", response_model=ApiResponse)
async def restart_agent(
    agent_id: str,
    current_user: dict = Depends(require_permission(Permission.AGENT_RESTART)),
    db: AsyncSession = Depends(get_db),
):
    """远程重启Agent."""
    result = await agent_service.restart_agent(db, agent_id, operator=current_user["username"])
    return ApiResponse(data=result)


@mgmt_router.get("/{agent_id}/tasks", response_model=ApiResponse[list[AgentTask]])
async def get_agent_tasks(
    agent_id: str,
    status: str = Query(None),
    task_type: str = Query(None, alias="type"),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Agent任务列表."""
    result = await agent_service.get_agent_tasks(db, agent_id, status, task_type)
    return ApiResponse(data=result)