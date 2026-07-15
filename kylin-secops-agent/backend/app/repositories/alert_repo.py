"""Alert repository."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import and_, case, desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert, AlertStatusHistory
from app.repositories.base import BaseRepository


class AlertRepository(BaseRepository[Alert]):
    """Alert data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(Alert, db)

    async def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
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
    ) -> tuple[Sequence[Alert], int]:
        """List alerts with comprehensive filters."""
        query = select(Alert).where(Alert.is_deleted == False)

        if status:
            statuses = [s.strip() for s in status.split(",")]
            query = query.where(Alert.status.in_(statuses))
        if severity:
            severities = [s.strip() for s in severity.split(",")]
            query = query.where(Alert.severity.in_(severities))
        if alert_type:
            types = [t.strip() for t in alert_type.split(",")]
            query = query.where(Alert.alert_type.in_(types))
        if agent_id:
            query = query.where(Alert.agent_id == agent_id)
        if mitre_technique:
            query = query.where(Alert.mitre_technique_id == mitre_technique)
        if assignee_id:
            query = query.where(Alert.assignee_id == uuid.UUID(str(assignee_id)))
        if start_time:
            query = query.where(Alert.created_at >= start_time)
        if end_time:
            query = query.where(Alert.created_at <= end_time)
        if keyword:
            query = query.where(
                or_(
                    Alert.title.ilike(f"%{keyword}%"),
                    Alert.description.ilike(f"%{keyword}%"),
                )
            )

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        # Sort
        sort_column = getattr(Alert, sort_by, Alert.created_at)
        if sort_order == "desc":
            query = query.order_by(desc(sort_column))
        else:
            query = query.order_by(sort_column)

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_stats(self, time_range: Optional[str] = None) -> Dict[str, Any]:
        """Get alert statistics."""
        query = select(Alert).where(Alert.is_deleted == False)

        if time_range:
            from app.services.alert_service import parse_time_range
            start = parse_time_range(time_range)
            if start:
                query = query.where(Alert.created_at >= start)

        # By severity
        severity_query = (
            select(Alert.severity, func.count().label("count"))
            .select_from(query.subquery())
            .group_by(Alert.severity)
        )
        severity_result = await self.db.execute(severity_query)
        by_severity = {row.severity: row.count for row in severity_result.all()}

        # By status
        status_query = (
            select(Alert.status, func.count().label("count"))
            .select_from(query.subquery())
            .group_by(Alert.status)
        )
        status_result = await self.db.execute(status_query)
        by_status = {row.status: row.count for row in status_result.all()}

        # By type
        type_query = (
            select(Alert.alert_type, func.count().label("count"))
            .select_from(query.subquery())
            .group_by(Alert.alert_type)
        )
        type_result = await self.db.execute(type_query)
        by_type = {row.alert_type: row.count for row in type_result.all()}

        total = await self.count({"is_deleted": False})
        if time_range:
            new_count = by_status.get("new", 0)
        else:
            new_query = select(func.count()).select_from(query.subquery()).where(Alert.status == "new")
            new_count = (await self.db.execute(new_query)).scalar() or 0

        return {
            "total": total,
            "by_severity": by_severity,
            "by_status": by_status,
            "by_type": by_type,
            "new_count": new_count,
            "critical_count": by_severity.get("critical", 0),
            "resolved_count": by_status.get("resolved", 0) + by_status.get("closed", 0),
            "avg_resolve_time_hours": None,
        }

    async def get_by_alert_seq(self, alert_seq: int) -> Optional[Alert]:
        result = await self.db.execute(
            select(Alert).where(Alert.alert_seq == alert_seq)
        )
        return result.scalar_one_or_none()

    async def get_related(self, alert_id: uuid.UUID) -> Sequence[Alert]:
        """Get related alerts by correlation key."""
        alert = await self.get(alert_id)
        if not alert or not alert.correlation_key:
            return []
        result = await self.db.execute(
            select(Alert).where(
                Alert.correlation_key == alert.correlation_key,
                Alert.is_deleted == False,
                Alert.id != alert_id,
            ).limit(20)
        )
        return result.scalars().all()


class AlertStatusHistoryRepository(BaseRepository[AlertStatusHistory]):
    """AlertStatusHistory data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(AlertStatusHistory, db)

    async def list_by_alert(
        self, alert_id: uuid.UUID
    ) -> Sequence[AlertStatusHistory]:
        result = await self.db.execute(
            select(AlertStatusHistory)
            .where(AlertStatusHistory.alert_id == alert_id)
            .order_by(desc(AlertStatusHistory.created_at))
        )
        return result.scalars().all()