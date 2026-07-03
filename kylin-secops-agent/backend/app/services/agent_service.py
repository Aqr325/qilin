"""Agent service: heartbeat, register, CRUD, upgrade, etc."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent, AgentHeartbeat
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

    agent = Agent(
        agent_id=req.agent_id,
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
        "credential": f"kylin_agent_{uuid.uuid4().hex}",
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
                from app.models.alerts import Alert
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

    # Load deployed policies for this agent
    from app.models.policy import Policy, PolicyDeployStatus
    from sqlalchemy import select
    stmt = (
        select(Policy, PolicyDeployStatus)
        .join(PolicyDeployStatus, Policy.id == PolicyDeployStatus.policy_id)
        .where(
            PolicyDeployStatus.agent_id == agent.id,
            PolicyDeployStatus.status == "deployed",
        )
    )
    results = await db.execute(stmt)
    policies = []
    for policy, deploy in results:
        policies.append({
            "id": str(policy.id),
            "name": policy.name,
            "type": policy.type,
            "rules": policy.rules,
            "config_version": deploy.config_version,
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
    """Upgrade agents."""
    agent_ids = req.get("agent_ids", [])
    target_version = req.get("target_version", "")
    if not agent_ids:
        return {"task_id": str(uuid.uuid4()), "scheduled_count": 0, "error": "No agents selected"}

    # In production: create upgrade tasks and notify agents via WebSocket
    return {
        "task_id": str(uuid.uuid4()),
        "scheduled_count": len(agent_ids),
        "target_version": target_version,
    }


async def get_upgrade_history(
    db: AsyncSession,
    agent_id: str,
) -> List[UpgradeRecord]:
    """Get upgrade history."""
    return []


async def restart_agent(
    db: AsyncSession,
    agent_id: str,
    operator: str,
) -> dict:
    """Restart agent."""
    # In production: send restart command via WebSocket
    return {"task_id": str(uuid.uuid4()), "agent_id": agent_id}


async def get_agent_tasks(
    db: AsyncSession,
    agent_id: str,
    status: Optional[str] = None,
    task_type: Optional[str] = None,
) -> List[AgentTask]:
    """Get agent tasks."""
    return []