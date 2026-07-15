"""Audit and Login log repository."""

import uuid
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import case, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog, LoginLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """AuditLog data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(AuditLog, db)

    async def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        result: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> tuple[Sequence[AuditLog], int]:
        """List audit logs with filters."""
        query = select(AuditLog)

        if user_id:
            query = query.where(AuditLog.user_id == uuid.UUID(str(user_id)))
        if action:
            query = query.where(AuditLog.action == action)
        if resource_type:
            query = query.where(AuditLog.resource_type == resource_type)
        if resource_id:
            query = query.where(AuditLog.resource_id == resource_id)
        if result:
            query = query.where(AuditLog.result == result)
        if start_time:
            query = query.where(AuditLog.created_at >= start_time)
        if end_time:
            query = query.where(AuditLog.created_at <= end_time)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_stats(self, time_range: Optional[str] = None) -> Dict[str, Any]:
        """Get audit statistics."""
        query = select(AuditLog)

        if time_range:
            from datetime import datetime, timezone, timedelta
            if time_range == "24h":
                start = datetime.now(timezone.utc) - timedelta(hours=24)
                query = query.where(AuditLog.created_at >= start)
            elif time_range == "7d":
                start = datetime.now(timezone.utc) - timedelta(days=7)
                query = query.where(AuditLog.created_at >= start)

        total_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(total_query)).scalar() or 0

        # By action
        action_result = await self.db.execute(
            select(AuditLog.action, func.count().label("count"))
            .select_from(query.subquery())
            .group_by(AuditLog.action)
        )
        by_action = {row.action: row.count for row in action_result.all()}

        # By resource
        resource_result = await self.db.execute(
            select(AuditLog.resource_type, func.count().label("count"))
            .select_from(query.subquery())
            .group_by(AuditLog.resource_type)
        )
        by_resource = {row.resource_type: row.count for row in resource_result.all()}

        # By user (top 10)
        user_result = await self.db.execute(
            select(AuditLog.username, func.count().label("count"))
            .select_from(query.subquery())
            .group_by(AuditLog.username)
            .order_by(desc("count"))
            .limit(10)
        )
        by_user = [{"username": row.username, "count": row.count} for row in user_result.all()]

        # Failure rate
        fail_result = await self.db.execute(
            select(func.count())
            .select_from(query.subquery())
            .where(AuditLog.result == "failure")
        )
        failures = fail_result.scalar() or 0

        return {
            "total": total,
            "by_action": by_action,
            "by_resource": by_resource,
            "by_user": by_user,
            "failure_rate": round(failures / total * 100, 2) if total > 0 else 0.0,
        }


class LoginLogRepository(BaseRepository[LoginLog]):
    """LoginLog data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(LoginLog, db)

    async def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        status: Optional[str] = None,
        ip_address: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> tuple[Sequence[LoginLog], int]:
        """List login logs with filters."""
        query = select(LoginLog)

        if user_id:
            query = query.where(LoginLog.user_id == uuid.UUID(str(user_id)))
        if username:
            query = query.where(LoginLog.username.ilike(f"%{username}%"))
        if status:
            query = query.where(LoginLog.status == status)
        if ip_address:
            query = query.where(LoginLog.ip_address == ip_address)
        if start_time:
            query = query.where(LoginLog.login_at >= start_time)
        if end_time:
            query = query.where(LoginLog.login_at <= end_time)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(desc(LoginLog.login_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total