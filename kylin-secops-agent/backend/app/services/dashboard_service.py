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
    high_alerts = await _count(db, Alert, Alert.severity == "high", Alert.is_deleted == False)
    medium_alerts = await _count(db, Alert, Alert.severity == "medium", Alert.is_deleted == False)
    low_alerts = await _count(db, Alert, Alert.severity == "low", Alert.is_deleted == False)
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
        high_alerts=high_alerts,
        medium_alerts=medium_alerts,
        low_alerts=low_alerts,
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
    """Get alert trend data (SQLite/PG 兼容：在 Python 端按天分桶)."""
    from sqlalchemy import select

    start = datetime.now(timezone.utc) - timedelta(days=days)
    result = await db.execute(
        select(Alert.created_at, Alert.severity)
        .where(Alert.created_at >= start, Alert.is_deleted == False)
    )

    buckets: Dict[str, Dict[str, int]] = {}
    for row in result.all():
        ts = row.created_at or datetime.now(timezone.utc)
        day_key = ts.strftime("%Y-%m-%d")
        buckets.setdefault(day_key, {})
        buckets[day_key][row.severity] = buckets[day_key].get(row.severity, 0) + 1

    labels = sorted(buckets.keys())
    return TrendData(
        labels=labels,
        datasets=[
            {"label": sev, "data": [buckets[d].get(sev, 0) for d in labels]}
            for sev in ["critical", "high", "medium", "low", "info"]
        ],
    )


async def get_agent_heatmap(db: AsyncSession, hours: int = 24) -> HeatmapData:
    """Get agent health heatmap (SQLite/PG 兼容：在 Python 端按小时分桶)."""
    from app.models.agent import AgentHeartbeat

    start = datetime.now(timezone.utc) - timedelta(hours=hours)
    result = await db.execute(
        select(AgentHeartbeat.agent_id, AgentHeartbeat.received_at, AgentHeartbeat.cpu_usage)
        .where(AgentHeartbeat.received_at >= start)
    )

    agent_map: Dict[str, Dict[str, list]] = {}
    time_slots_set: set = set()
    for row in result.all():
        ts = row.received_at or datetime.now(timezone.utc)
        hour_key = ts.strftime("%Y-%m-%d %H:00")
        time_slots_set.add(hour_key)
        agent_map.setdefault(row.agent_id, {}).setdefault(hour_key, [])
        if row.cpu_usage is not None:
            agent_map[row.agent_id][hour_key].append(row.cpu_usage)

    sorted_agents = sorted(agent_map.keys())[:20]
    sorted_slots = sorted(time_slots_set)
    data = [
        [
            (round(sum(agent_map[a][s]) / len(agent_map[a][s]), 2) if agent_map[a].get(s) else 0.0)
            for s in sorted_slots
        ]
        for a in sorted_agents
    ]

    return HeatmapData(
        time_slots=sorted_slots,
        agents=sorted_agents,
        data=data,
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