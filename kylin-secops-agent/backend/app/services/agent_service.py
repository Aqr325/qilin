"""Agent service: heartbeat, register, CRUD, upgrade, etc."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentHeartbeat, AgentTask as AgentTaskModel
from app.repositories.agent_repo import AgentRepository, AgentHeartbeatRepository
from app.schemas.agent import (
    AgentDetail,
    AgentGlobalStats,
    AgentMetrics,
    AgentRegisterRequest,
    AgentSummary,
    AgentTask,
    HealthOverview,
    HeartbeatRecord,
    HeartbeatRequest,
    HeartbeatResponse,
    OnlineMapItem,
    UpgradeRecord,
)
from app.schemas.common import Page
from app.services.websocket_service import ws_manager


async def process_heartbeat(
    db: AsyncSession,
    req: HeartbeatRequest,
    ip_address: Optional[str] = None,
) -> HeartbeatResponse:
    """Process agent heartbeat."""
    agent_repo = AgentRepository(db)
    hb_repo = AgentHeartbeatRepository(db)

    agent_id = req.agentId
    agent = await agent_repo.get_by_agent_id(agent_id)

    if not agent:
        # Auto-register unknown agents
        agent = Agent(
            agent_id=agent_id,
            credential=f"kylin_agent_{uuid.uuid4().hex}",
            hostname=agent_id,
            ip_address=ip_address,
            os_version="unknown",
            agent_version=req.version or "0.0.0",
            cpu_cores=req.cpu.get("cores", 0),
            total_memory=req.memory.get("total", 0),
            status="online",
        )
        db.add(agent)
        await db.flush()
    else:
        # Update status
        old_status = agent.status
        agent.status = "online"
        agent.last_heartbeat = datetime.now(timezone.utc)
        if ip_address:
            agent.last_heartbeat_ip = ip_address
        if req.version:
            agent.agent_version = req.version
        await db.flush()

        # Broadcast status change if needed
        if old_status != "online":
            await ws_manager.broadcast("agent.status", {
                "agent_id": agent_id,
                "old_status": old_status,
                "new_status": "online",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # Record heartbeat
    hb = AgentHeartbeat(
        agent_id=agent_id,
        cpu_usage=req.cpu.get("usage"),
        cpu_cores=req.cpu.get("cores"),
        memory_total=req.memory.get("total"),
        memory_used=req.memory.get("used"),
        memory_percent=req.memory.get("percent"),
        disk_json=req.disk if req.disk else None,
        processes_total=req.processes.get("total"),
        processes_running=req.processes.get("running"),
        agent_version=req.version,
        payload=req.model_dump(),
        ip_address=ip_address,
    )
    db.add(hb)
    await db.flush()

    return HeartbeatResponse(
        server_time=datetime.now(timezone.utc).isoformat(),
        next_heartbeat_interval=10,
        config_version=agent.config_version,
        config_update_required=False,
        pending_tasks=[],
        ack_action="continue",
    )


async def register_agent(
    db: AsyncSession,
    req: AgentRegisterRequest,
) -> dict:
    """Register a new agent."""
    agent_repo = AgentRepository(db)
    existing = await agent_repo.get_by_agent_id(req.agent_id)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent {req.agent_id} already registered",
        )

    credential = f"kylin_agent_{uuid.uuid4().hex}"
    agent = Agent(
        agent_id=req.agent_id,
        credential=credential,
        hostname=req.hostname,
        ip_address=req.ip_address,
        os_version=req.os_version,
        kernel_version=req.kernel_version,
        agent_version=req.agent_version,
        cpu_cores=req.cpu_cores,
        total_memory=req.total_memory,
        disk_total=req.disk_total,
        status="online",
        tags=req.tags,
    )
    db.add(agent)
    await db.flush()

    return {
        "agent_id": agent.agent_id,
        "credential": credential,
        "config": {
            "heartbeat_interval": 10,
            "log_level": "info",
        },
    }


async def process_batch_events(
    db: AsyncSession,
    req: "AgentBatchEventsRequest",
) -> dict:
    """Process batch events from agent."""
    events = req.events if hasattr(req, 'events') else (req.get('events', []) if isinstance(req, dict) else [])
    received = len(events)
    failed = 0
    processed = 0

    for event in events:
        try:
            event_type = event.get("type", "")
            if event_type == "alert":
                from app.models.alert import Alert
                import uuid
                alert = Alert(
                    id=uuid.uuid4(),
                    source=event.get("source", ""),
                    level=event.get("level", "medium"),
                    title=event.get("title", "未知告警"),
                    description=event.get("description", ""),
                    status="pending",
                )
                db.add(alert)
                await db.flush()
            processed += 1
        except Exception:
            failed += 1

    return {"received": received, "processed": processed, "failed": failed}


async def get_agent_config(
    db: AsyncSession,
    agent_id: str,
) -> dict:
    """Get agent configuration."""
    agent_repo = AgentRepository(db)
    agent = await agent_repo.get_by_agent_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    # Load deployed policies for this agent (关联 PolicyTarget 下发记录)
    from app.models.policy import Policy, PolicyTarget
    from sqlalchemy import select
    stmt = (
        select(Policy, PolicyTarget)
        .join(PolicyTarget, Policy.id == PolicyTarget.policy_id)
        .where(
            PolicyTarget.agent_id == agent.agent_id,
            PolicyTarget.status == "deployed",
        )
    )
    results = await db.execute(stmt)
    policies = []
    for policy, deploy in results:
        policies.append({
            "id": str(policy.id),
            "name": policy.name,
            "type": policy.policy_type,
            "rules": policy.rules,
            "config_version": deploy.deployed_version,
        })

    return {
        "agent_id": agent.agent_id,
        "config_version": agent.config_version,
        "heartbeat_interval": 10,
        "policies": policies,
    }


async def process_task_result(
    db: AsyncSession,
    agent_id: str,
    req: dict,
) -> dict:
    """Process task result from agent."""
    task_id = req.get("task_id", "")
    status = req.get("status", "")
    result_data = req.get("result", {})
    error_msg = req.get("error", "")

    if not task_id:
        return {"message": "Missing task_id", "success": False}

    return {
        "message": f"Task result received: {task_id}",
        "task_id": task_id,
        "status": status,
        "success": status == "success",
    }


async def list_agents(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    status: Optional[str] = None,
    version: Optional[str] = None,
    keyword: Optional[str] = None,
    os_version: Optional[str] = None,
) -> Page[AgentSummary]:
    """List agents with pagination and filters."""
    agent_repo = AgentRepository(db)
    skip = (page - 1) * size
    agents, total = await agent_repo.list_paginated(
        skip=skip, limit=size,
        status=status, version=version,
        keyword=keyword, os_version=os_version,
    )

    items = [
        AgentSummary(
            id=str(a.id),
            agent_id=a.agent_id,
            hostname=a.hostname,
            ip_address=str(a.ip_address) if a.ip_address else None,
            os_version=a.os_version,
            agent_version=a.agent_version,
            status=a.status,
            cpu_cores=a.cpu_cores,
            total_memory=a.total_memory,
            last_heartbeat=a.last_heartbeat,
            tags=a.tags,
            registered_at=a.registered_at,
        )
        for a in agents
    ]
    return Page.create(items, total, page, size)


async def get_global_stats(db: AsyncSession) -> AgentGlobalStats:
    """Get global agent statistics."""
    agent_repo = AgentRepository(db)
    stats = await agent_repo.get_stats()
    return AgentGlobalStats(**stats)


async def get_health_overview(db: AsyncSession) -> HealthOverview:
    """Get health overview."""
    agent_repo = AgentRepository(db)
    stats = await agent_repo.get_stats()
    return HealthOverview(
        total_agents=stats["total"],
        online_agents=stats["online"],
        offline_agents=stats["offline"],
        error_agents=stats["error"],
        online_rate=stats["online_rate"],
        versions=stats.get("versions", []),
    )


async def get_online_map(db: AsyncSession) -> List[OnlineMapItem]:
    """Get online agent map."""
    agent_repo = AgentRepository(db)
    agents, _ = await agent_repo.list_paginated(limit=1000)
    return [
        OnlineMapItem(
            agent_id=a.agent_id,
            hostname=a.hostname,
            ip_address=str(a.ip_address) if a.ip_address else None,
            status=a.status,
            last_heartbeat=a.last_heartbeat,
            os_version=a.os_version,
        )
        for a in agents
    ]


async def get_agent_detail(
    db: AsyncSession,
    agent_id: str,
) -> AgentDetail:
    """Get agent detail."""
    agent_repo = AgentRepository(db)
    agent = await agent_repo.get_by_agent_id(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return AgentDetail(
        id=str(agent.id),
        agent_id=agent.agent_id,
        hostname=agent.hostname,
        ip_address=str(agent.ip_address) if agent.ip_address else None,
        os_version=agent.os_version,
        kernel_version=agent.kernel_version,
        agent_version=agent.agent_version,
        cpu_cores=agent.cpu_cores,
        total_memory=agent.total_memory,
        disk_total=agent.disk_total,
        status=agent.status,
        last_heartbeat=agent.last_heartbeat,
        last_heartbeat_ip=str(agent.last_heartbeat_ip) if agent.last_heartbeat_ip else None,
        registered_at=agent.registered_at,
        first_seen_at=agent.first_seen_at,
        tags=agent.tags,
        config_version=agent.config_version,
        is_deleted=agent.is_deleted,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


async def get_agent_metrics(
    db: AsyncSession,
    agent_id: str,
    time_range: Optional[str] = None,
) -> AgentMetrics:
    """Get agent metrics."""
    hb_repo = AgentHeartbeatRepository(db)
    hb = await hb_repo.get_latest(agent_id)
    if not hb:
        return AgentMetrics()
    return AgentMetrics(
        cpu_usage=hb.cpu_usage,
        memory_usage=hb.memory_percent,
        memory_total=hb.memory_total,
        memory_used=hb.memory_used,
        disk_usage=hb.disk_json,
        processes_total=hb.processes_total,
        processes_running=hb.processes_running,
        last_report_at=hb.received_at,
    )


async def get_heartbeat_history(
    db: AsyncSession,
    agent_id: str,
    page: int = 1,
    size: int = 20,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
) -> Page[HeartbeatRecord]:
    """Get heartbeat history."""
    hb_repo = AgentHeartbeatRepository(db)
    skip = (page - 1) * size
    records, total = await hb_repo.list_by_agent(
        agent_id, skip=skip, limit=size,
        start_time=start_time, end_time=end_time,
    )
    items = [
        HeartbeatRecord(
            id=r.id,
            agent_id=r.agent_id,
            received_at=r.received_at,
            cpu_usage=r.cpu_usage,
            memory_percent=r.memory_percent,
            processes_total=r.processes_total,
            agent_version=r.agent_version,
        )
        for r in records
    ]
    return Page.create(items, total, page, size)


async def upgrade_agents(
    db: AsyncSession,
    req: dict,
    operator: str,
) -> dict:
    """升级Agent：持久化升级任务并标记Agent为 upgrading，便于追踪与心跳对账。"""
    # 路由传入的是 Pydantic AgentUpgradeRequest，统一规整为 dict 以兼容既有逻辑
    if not isinstance(req, dict):
        req = {
            "agent_ids": list(req.agent_ids),
            "target_version": getattr(req, "version", ""),
            "package_url": req.package_url,
        }
    agent_repo = AgentRepository(db)
    agent_ids = req.get("agent_ids", [])
    target_version = req.get("target_version", "")
    package_url = req.get("package_url", "")

    if not agent_ids:
        return {
            "task_id": "",
            "scheduled_count": 0,
            "target_version": target_version,
            "tasks": [],
        }

    tasks: List[AgentTaskModel] = []
    for aid in agent_ids:
        agent = await agent_repo.get_by_agent_id(aid)
        from_version = agent.agent_version if agent else None
        if agent:
            # 标记为升级中；Agent下次心跳上报会自动恢复为 online
            agent.status = "upgrading"
        task = AgentTaskModel(
            agent_id=aid,
            task_type="upgrade",
            status="pending",
            params={
                "from_version": from_version,
                "target_version": target_version,
                "package_url": package_url,
            },
            created_by=str(operator) if operator else None,
        )
        db.add(task)
        tasks.append(task)

    await db.flush()
    task_ids = [t.id for t in tasks]
    return {
        "task_id": task_ids[0] if task_ids else "",
        "scheduled_count": len(tasks),
        "target_version": target_version,
        "tasks": task_ids,
    }


async def get_upgrade_history(
    db: AsyncSession,
    agent_id: str,
) -> List[UpgradeRecord]:
    """获取Agent升级历史（来自 agent_tasks）。"""
    from sqlalchemy import select, desc

    result = await db.execute(
        select(AgentTaskModel)
        .where(AgentTaskModel.agent_id == agent_id, AgentTaskModel.task_type == "upgrade")
        .order_by(desc(AgentTaskModel.created_at))
    )
    rows = result.scalars().all()
    return [
        UpgradeRecord(
            task_id=r.id,
            agent_id=r.agent_id,
            from_version=(r.params or {}).get("from_version"),
            to_version=(r.params or {}).get("target_version"),
            status=r.status,
            created_at=r.created_at,
            completed_at=r.completed_at,
        )
        for r in rows
    ]


async def restart_agent(
    db: AsyncSession,
    agent_id: str,
    operator: str,
) -> dict:
    """重启Agent：持久化重启任务，便于追踪。"""
    agent_repo = AgentRepository(db)
    agent = await agent_repo.get_by_agent_id(agent_id)
    task = AgentTaskModel(
        agent_id=agent_id,
        task_type="restart",
        status="pending",
        params={},
        created_by=str(operator) if operator else None,
    )
    db.add(task)
    await db.flush()
    return {"task_id": task.id, "agent_id": agent_id}


async def get_agent_tasks(
    db: AsyncSession,
    agent_id: str,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
) -> List[AgentTask]:
    """获取Agent任务列表（来自 agent_tasks）。"""
    from sqlalchemy import select, desc

    stmt = select(AgentTaskModel).where(AgentTaskModel.agent_id == agent_id)
    if status:
        stmt = stmt.where(AgentTaskModel.status == status)
    if task_type:
        stmt = stmt.where(AgentTaskModel.task_type == task_type)
    stmt = stmt.order_by(desc(AgentTaskModel.created_at))
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [
        AgentTask(
            task_id=r.id,
            type=r.task_type,
            status=r.status,
            created_at=r.created_at,
            params=r.params,
        )
        for r in rows
    ]