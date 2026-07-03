"""Alert service: CRUD, status management, MITRE, timeline, export."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertStatusHistory
from app.repositories.alert_repo import AlertRepository, AlertStatusHistoryRepository
from app.schemas.alert import (
    AlertDetail,
    AlertStats,
    AlertStatusChange,
    AlertSummary,
    BatchStatusResult,
    MitreMatrixItem,
    SuppressRule,
    TimelineData,
)
from app.schemas.common import Page, FilterSummary
from app.services.websocket_service import ws_manager


ALERT_STATUS_FLOW = {
    "new": ["acknowledged", "investigating", "resolved", "false_positive", "closed"],
    "acknowledged": ["investigating", "resolved", "false_positive", "closed"],
    "investigating": ["resolved", "false_positive", "closed"],
    "resolved": ["closed"],
    "false_positive": ["closed"],
    "closed": [],
}

ALERT_TYPE_LABELS = {
    "file_monitor": "文件监控告警",
    "process_monitor": "进程异常告警",
    "network_monitor": "网络连接异常",
    "login_monitor": "登录行为异常",
    "user_monitor": "用户行为异常",
    "vulnerability": "漏洞告警",
    "malware": "恶意软件告警",
    "privilege_escalation": "提权告警",
    "lateral_movement": "横向移动告警",
    "persistence": "持久化告警",
    "defense_evasion": "防御规避告警",
    "anomaly": "行为异常告警",
}

SEVERITY_LABELS = {
    "critical": "致命",
    "high": "高",
    "medium": "中",
    "low": "低",
    "info": "信息",
}

STATUS_LABELS = {
    "new": "待处理",
    "acknowledged": "已确认",
    "investigating": "调查中",
    "resolved": "已解决",
    "false_positive": "误报",
    "closed": "已关闭",
}


def parse_time_range(time_range: str) -> Optional[datetime]:
    """Parse time range string."""
    now = datetime.now(timezone.utc)
    ranges = {
        "1h": 3600, "24h": 86400, "7d": 604800, "30d": 2592000,
    }
    if time_range in ranges:
        from datetime import timedelta
        return now - timedelta(seconds=ranges[time_range])
    return None


async def list_alerts(
    db: AsyncSession,
    page: int = 1,
    size: int = 20,
    status: Optional[str] = None,
    severity: Optional[str] = None,
    alert_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    mitre_technique: Optional[str] = None,
    keyword: Optional[str] = None,
    assignee_id: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Page[AlertSummary]:
    """List alerts with filters."""
    repo = AlertRepository(db)
    skip = (page - 1) * size
    alerts, total = await repo.list_paginated(
        skip=skip, limit=size,
        status=status, severity=severity, alert_type=alert_type,
        agent_id=agent_id, start_time=start_time, end_time=end_time,
        mitre_technique=mitre_technique, keyword=keyword,
        assignee_id=assignee_id, sort_by=sort_by, sort_order=sort_order,
    )

    items = [
        AlertSummary(
            id=str(a.id),
            alert_seq=a.alert_seq,
            agent_id=a.agent_id,
            alert_type=a.alert_type,
            alert_type_label=ALERT_TYPE_LABELS.get(a.alert_type),
            severity=a.severity,
            severity_label=SEVERITY_LABELS.get(a.severity),
            title=a.title,
            description=a.description,
            status=a.status,
            status_label=STATUS_LABELS.get(a.status),
            mitre_technique_id=a.mitre_technique_id,
            mitre_tactic=a.mitre_tactic,
            mitre_technique_name=a.mitre_technique_name,
            suppressed=a.suppressed,
            correlation_count=a.correlation_count,
            first_detected_at=a.first_detected_at,
            last_detected_at=a.last_detected_at,
            alert_count=a.alert_count,
            source_ip=a.source_ip,
            created_at=a.created_at,
        )
        for a in alerts
    ]
    return Page.create(items, total, page, size)


async def get_stats(db: AsyncSession, time_range: Optional[str] = None) -> AlertStats:
    """Get alert statistics."""
    repo = AlertRepository(db)
    stats = await repo.get_stats(time_range)
    return AlertStats(**stats)


async def get_alert_detail(db: AsyncSession, alert_id: str) -> AlertDetail:
    """Get alert detail."""
    repo = AlertRepository(db)
    try:
        alert = await repo.get(uuid.UUID(alert_id))
    except ValueError:
        alert = await repo.get_by_alert_seq(int(alert_id))

    if not alert or alert.is_deleted:
        raise HTTPException(status_code=404, detail="告警不存在")

    assignee_info = None
    if alert.assignee_id:
        assignee_info = {"id": str(alert.assignee_id)}

    return AlertDetail(
        id=str(alert.id),
        alert_seq=alert.alert_seq,
        agent_id=alert.agent_id,
        alert_type=alert.alert_type,
        alert_type_label=ALERT_TYPE_LABELS.get(alert.alert_type),
        severity=alert.severity,
        severity_label=SEVERITY_LABELS.get(alert.severity),
        title=alert.title,
        description=alert.description,
        detail=alert.detail,
        source=alert.source,
        status=alert.status,
        status_label=STATUS_LABELS.get(alert.status),
        status_changed_at=alert.status_changed_at,
        mitre_technique_id=alert.mitre_technique_id,
        mitre_tactic=alert.mitre_tactic,
        mitre_technique_name=alert.mitre_technique_name,
        assignee=assignee_info,
        assigned_at=alert.assigned_at,
        suppressed=alert.suppressed,
        suppressed_until=alert.suppressed_until,
        suppress_reason=alert.suppress_reason,
        resolved_at=alert.resolved_at,
        correlation_key=alert.correlation_key,
        correlation_count=alert.correlation_count,
        first_detected_at=alert.first_detected_at,
        last_detected_at=alert.last_detected_at,
        alert_count=alert.alert_count,
        source_ip=alert.source_ip,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
    )


async def update_status(
    db: AsyncSession,
    alert_id: str,
    new_status: str,
    comment: Optional[str] = None,
    operator: Optional[dict] = None,
) -> AlertDetail:
    """Update alert status."""
    repo = AlertRepository(db)
    alert = await repo.get(uuid.UUID(alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    if new_status not in ALERT_STATUS_FLOW.get(alert.status, []):
        raise HTTPException(
            status_code=400,
            detail=f"不能从 {STATUS_LABELS.get(alert.status, alert.status)} 转换到 {STATUS_LABELS.get(new_status, new_status)}",
        )

    old_status = alert.status
    alert.status = new_status
    alert.status_changed_at = datetime.now(timezone.utc)

    if new_status in ("resolved", "closed"):
        alert.resolved_at = datetime.now(timezone.utc)
        if operator:
            from app.models.user import User
            alert.resolved_by = uuid.UUID(operator["id"])

    await db.flush()

    # Record history
    history = AlertStatusHistory(
        alert_id=alert.id,
        from_status=old_status,
        to_status=new_status,
        operator_id=uuid.UUID(operator["id"]) if operator else None,
        operator_name=operator.get("username") if operator else None,
        operation=f"status_change:{old_status}->{new_status}",
        comment=comment,
        source="manual",
    )
    db.add(history)
    await db.flush()

    # Broadcast via WebSocket
    await ws_manager.broadcast("alert.updated", {
        "alert_id": str(alert.id),
        "old_status": old_status,
        "new_status": new_status,
        "operator": operator.get("username") if operator else None,
    })

    return await get_alert_detail(db, alert_id)


async def batch_update_status(
    db: AsyncSession,
    alert_ids: List[str],
    target_status: str,
    comment: Optional[str] = None,
    operator: Optional[dict] = None,
    notify: bool = False,
) -> BatchStatusResult:
    """Batch update alert statuses."""
    repo = AlertRepository(db)
    processed = 0
    failed = 0
    details = []

    for alert_id in alert_ids:
        try:
            detail = await update_status(db, alert_id, target_status, comment, operator)
            details.append({
                "alert_id": alert_id,
                "success": True,
                "from_status": detail.status,
                "to_status": target_status,
            })
            processed += 1
        except HTTPException as e:
            details.append({
                "alert_id": alert_id,
                "success": False,
                "error": e.detail,
            })
            failed += 1

    return BatchStatusResult(
        total=len(alert_ids),
        processed=processed,
        failed=failed,
        details=details,
    )


async def assign_alert(
    db: AsyncSession,
    alert_id: str,
    assignee_id: str,
    operator: Optional[dict] = None,
) -> AlertDetail:
    """Assign alert to user."""
    repo = AlertRepository(db)
    alert = await repo.get(uuid.UUID(alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    alert.assignee_id = uuid.UUID(assignee_id)
    alert.assigned_at = datetime.now(timezone.utc)
    await db.flush()

    return await get_alert_detail(db, alert_id)


async def get_status_history(
    db: AsyncSession,
    alert_id: str,
) -> List[AlertStatusChange]:
    """Get alert status change history."""
    history_repo = AlertStatusHistoryRepository(db)
    records = await history_repo.list_by_alert(uuid.UUID(alert_id))
    return [
        AlertStatusChange(
            id=r.id,
            from_status=r.from_status,
            to_status=r.to_status,
            operator_name=r.operator_name,
            operation=r.operation,
            comment=r.comment,
            source=r.source,
            created_at=r.created_at,
        )
        for r in records
    ]


async def get_related_alerts(
    db: AsyncSession,
    alert_id: str,
) -> List[AlertSummary]:
    """Get related alerts by correlation key."""
    repo = AlertRepository(db)
    related = await repo.get_related(uuid.UUID(alert_id))
    return [
        AlertSummary(
            id=str(a.id),
            alert_seq=a.alert_seq,
            agent_id=a.agent_id,
            alert_type=a.alert_type,
            alert_type_label=ALERT_TYPE_LABELS.get(a.alert_type),
            severity=a.severity,
            severity_label=SEVERITY_LABELS.get(a.severity),
            title=a.title,
            description=a.description,
            status=a.status,
            status_label=STATUS_LABELS.get(a.status),
            suppressed=a.suppressed,
            created_at=a.created_at,
        )
        for a in related
    ]


async def suppress_alert(
    db: AsyncSession,
    alert_id: str,
    rule_config: Dict[str, Any],
    expire_time: Optional[datetime] = None,
    operator: Optional[dict] = None,
) -> SuppressRule:
    """Suppress an alert."""
    repo = AlertRepository(db)
    alert = await repo.get(uuid.UUID(alert_id))
    if not alert:
        raise HTTPException(status_code=404, detail="告警不存在")

    alert.suppressed = True
    alert.suppressed_until = expire_time
    alert.suppress_reason = str(rule_config)
    await db.flush()

    return SuppressRule(
        id=str(uuid.uuid4()),
        alert_id=alert_id,
        rule_config=rule_config,
        expire_time=expire_time,
    )


async def get_mitre_matrix(db: AsyncSession) -> List[MitreMatrixItem]:
    """Get MITRE ATT&CK matrix from alerts."""
    from sqlalchemy import func, select
    from app.models.alert import Alert

    result = await db.execute(
        select(
            Alert.mitre_tactic,
            Alert.mitre_technique_id,
            Alert.mitre_technique_name,
            func.count().label("count"),
        )
        .where(
            Alert.mitre_technique_id.isnot(None),
            Alert.is_deleted == False,
        )
        .group_by(Alert.mitre_tactic, Alert.mitre_technique_id, Alert.mitre_technique_name)
    )

    tactic_map: Dict[str, List[Dict]] = {}
    for row in result.all():
        tactic = row.mitre_tactic or "unknown"
        if tactic not in tactic_map:
            tactic_map[tactic] = []
        tactic_map[tactic].append({
            "technique_id": row.mitre_technique_id,
            "technique_name": row.mitre_technique_name,
            "count": row.count,
        })

    return [
        MitreMatrixItem(tactic_id=t, tactic_name=t, techniques=techs)
        for t, techs in tactic_map.items()
    ]


async def get_timeline(
    db: AsyncSession,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = "1h",
) -> TimelineData:
    """Get alert timeline data."""
    from sqlalchemy import func, select, text
    from app.models.alert import Alert

    query = select(
        func.date_trunc(text(":interval"), Alert.created_at).label("bucket"),
        Alert.severity,
        func.count().label("count"),
    ).where(Alert.is_deleted == False)

    if start_time:
        query = query.where(Alert.created_at >= start_time)
    if end_time:
        query = query.where(Alert.created_at <= end_time)

    query = query.group_by("bucket", Alert.severity).order_by("bucket")

    result = await db.execute(query, {"interval": interval})
    buckets: Dict[str, Dict[str, int]] = {}
    for row in result.all():
        bucket_key = str(row.bucket)
        if bucket_key not in buckets:
            buckets[bucket_key] = {}
        buckets[bucket_key][row.severity] = row.count

    return TimelineData(
        timestamps=list(buckets.keys()),
        series=[
            {"name": sev, "data": [b.get(sev, 0) for b in buckets.values()]}
            for sev in ["critical", "high", "medium", "low", "info"]
        ],
    )


async def export_alerts(
    db: AsyncSession,
    format: str = "csv",
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
):
    """Export alerts as CSV/XLSX."""
    from fastapi.responses import StreamingResponse
    import io
    import csv

    repo = AlertRepository(db)
    alerts, _ = await repo.list_paginated(
        skip=0, limit=10000,
        start_time=start_time, end_time=end_time,
        severity=severity, status=status,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["alert_seq", "agent_id", "alert_type", "severity", "title",
                     "status", "mitre_technique_id", "created_at"])
    for a in alerts:
        writer.writerow([
            a.alert_seq, a.agent_id, a.alert_type, a.severity, a.title,
            a.status, a.mitre_technique_id, a.created_at.isoformat() if a.created_at else "",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=alerts_export.csv"},
    )