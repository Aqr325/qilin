"""Dashboard service: overview, trends, heatmap, top alerts."""

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent import Agent
from app.models.alert import Alert
from app.schemas.ai import DashboardOverview, HeatmapData, TopAlertType, TrendData


async def get_overview(db: AsyncSession) -> DashboardOverview:
    """Get dashboard overview data."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # Alert counts
    total_alerts = await _count(db, Alert, Alert.is_deleted == False)
    active_alerts = await _count(db, Alert, Alert.status.in_(["new", "acknowledged", "investigating"]))
    critical_alerts = await _count(db, Alert, Alert.severity == "critical", Alert.is_deleted == False)
    resolved_alerts = await _count(db, Alert, Alert.status.in_(["resolved", "closed"]))
    alerts_today = await _count(db, Alert, Alert.created_at >= today_start)
    resolved_today = await _count(db, Alert, Alert.created_at >= today_start, Alert.status == "resolved")

    # Agent counts
    total_agents = await _count(db, Agent, Agent.is_deleted == False)
    online_agents = await _count(db, Agent, Agent.status == "online", Agent.is_deleted == False)
    offline_agents = await _count(db, Agent, Agent.status == "offline", Agent.is_deleted == False)

    return DashboardOverview(
        total_alerts=total_alerts,
        active_alerts=active_alerts,
        critical_alerts=critical_alerts,
        resolved_alerts=resolved_alerts,
        total_agents=total_agents,
        online_agents=online_agents,
        offline_agents=offline_agents,
        active_policies=0,
        alerts_today=alerts_today,
        resolved_today=resolved_today,
        avg_response_time_hours=None,
    )


async def get_alert_trend(db: AsyncSession, days: int = 7) -> TrendData:
    """Get alert trend data."""
    from sqlalchemy import func, text

    start = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(
            func.date_trunc("day", Alert.created_at).label("day"),
            Alert.severity,
            func.count().label("count"),
        )
        .where(Alert.created_at >= start, Alert.is_deleted == False)
        .group_by("day", Alert.severity)
        .order_by("day")
    )

    buckets: Dict[str, Dict[str, int]] = {}
    for row in result.all():
        day_key = str(row.day)[:10]
        if day_key not in buckets:
            buckets[day_key] = {}
        buckets[day_key][row.severity] = row.count

    return TrendData(
        labels=list(buckets.keys()),
        datasets=[
            {"label": sev, "data": [b.get(sev, 0) for b in buckets.values()]}
            for sev in ["critical", "high", "medium", "low", "info"]
        ],
    )


async def get_agent_heatmap(db: AsyncSession, hours: int = 24) -> HeatmapData:
    """Get agent health heatmap."""
    from app.models.agent import AgentHeartbeat

    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(
            AgentHeartbeat.agent_id,
            func.date_trunc("hour", AgentHeartbeat.received_at).label("hour"),
            func.avg(AgentHeartbeat.cpu_usage).label("avg_cpu"),
        )
        .where(AgentHeartbeat.received_at >= start)
        .group_by(AgentHeartbeat.agent_id, "hour")
    )

    agent_map: Dict[str, Dict[str, float]] = {}
    time_slots_set: set = set()
    for row in result.all():
        agent_id = row.agent_id
        hour_key = str(row.hour)
        time_slots_set.add(hour_key)
        if agent_id not in agent_map:
            agent_map[agent_id] = {}
        agent_map[agent_id][hour_key] = row.avg_cpu or 0.0

    sorted_agents = sorted(agent_map.keys())[:20]
    sorted_slots = sorted(time_slots_set)

    return HeatmapData(
        time_slots=sorted_slots,
        agents=sorted_agents,
        data=[
            [agent_map[a].get(s, 0.0) for s in sorted_slots]
            for a in sorted_agents
        ],
    )


async def get_top_alerts(
    db: AsyncSession,
    limit: int = 10,
    time_range: str = "24h",
) -> List[TopAlertType]:
    """Get top alert types."""
    from sqlalchemy import func, desc

    now = datetime.now(timezone.utc)
    if time_range == "7d":
        start = now - timedelta(days=7)
    elif time_range == "30d":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(hours=24)

    result = await db.execute(
        select(
            Alert.alert_type,
            func.count().label("count"),
        )
        .where(Alert.created_at >= start, Alert.is_deleted == False)
        .group_by(Alert.alert_type)
        .order_by(desc("count"))
        .limit(limit)
    )

    return [
        TopAlertType(
            alert_type=row.alert_type,
            count=row.count,
        )
        for row in result.all()
    ]


async def _count(db, model, *filters) -> int:
    """Helper to count records."""
    query = select(func.count()).select_from(model)
    for f in filters:
        query = query.where(f)
    result = await db.execute(query)
    return result.scalar() or 0