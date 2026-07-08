"""Agent repository."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent import Agent, AgentHeartbeat
from app.repositories.base import BaseRepository


class AgentRepository(BaseRepository[Agent]):
    """Agent data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(Agent, db)

    async def get_by_agent_id(self, agent_id: str) -> Optional[Agent]:
        """Get agent by its unique agent_id."""
        result = await self.db.execute(
            select(Agent).where(
                Agent.agent_id == agent_id,
                Agent.is_deleted == False,
            )
        )
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        version: Optional[str] = None,
        keyword: Optional[str] = None,
        os_version: Optional[str] = None,
    ) -> tuple[Sequence[Agent], int]:
        """List agents with filters."""
        query = select(Agent).where(Agent.is_deleted == False)

        if status:
            query = query.where(Agent.status == status)
        if version:
            query = query.where(Agent.agent_version == version)
        if os_version:
            query = query.where(Agent.os_version == os_version)
        if keyword:
            query = query.where(
                or_(
                    Agent.hostname.ilike(f"%{keyword}%"),
                    Agent.agent_id.ilike(f"%{keyword}%"),
                    Agent.ip_address.ilike(f"%{keyword}%"),
                )
            )

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(desc(Agent.last_heartbeat)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def get_stats(self) -> Dict[str, Any]:
        """Get agent global statistics."""
        result = await self.db.execute(
            select(
                func.count().label("total"),
                func.sum(case((Agent.status == "online", 1), else_=0)).label("online"),
                func.sum(case((Agent.status == "offline", 1), else_=0)).label("offline"),
                func.sum(case((Agent.status == "error", 1), else_=0)).label("error"),
                func.sum(case((Agent.status == "upgrading", 1), else_=0)).label("upgrading"),
            ).where(Agent.is_deleted == False)
        )
        row = result.one()

        # Version distribution
        version_query = await self.db.execute(
            select(Agent.agent_version, func.count().label("count"))
            .where(Agent.is_deleted == False)
            .group_by(Agent.agent_version)
        )
        versions = [{"version": v, "count": c} for v, c in version_query.all()]

        # OS version distribution
        os_query = await self.db.execute(
            select(Agent.os_version, func.count().label("count"))
            .where(Agent.is_deleted == False)
            .group_by(Agent.os_version)
        )
        os_versions = [{"os_version": v, "count": c} for v, c in os_query.all()]

        total = row.total or 0
        online = row.online or 0
        return {
            "total": total,
            "online": online,
            "offline": row.offline or 0,
            "error": row.error or 0,
            "upgrading": row.upgrading or 0,
            "online_rate": round(online / total * 100, 2) if total > 0 else 0.0,
            "versions": versions,
            "os_versions": os_versions,
        }

    async def update_status(
        self, agent_id: str, status: str, ip_address: Optional[str] = None
    ) -> Optional[Agent]:
        """Update agent status and heartbeat."""
        agent = await self.get_by_agent_id(agent_id)
        if agent:
            old_status = agent.status
            agent.status = status
            agent.last_heartbeat = datetime.now(timezone.utc)
            if ip_address:
                agent.last_heartbeat_ip = ip_address
            await self.db.flush()
            return agent, old_status
        return None, None

    async def mark_offline(self, agent_id: str) -> bool:
        """Mark agent as offline."""
        agent = await self.get_by_agent_id(agent_id)
        if agent and agent.status != "offline":
            agent.status = "offline"
            await self.db.flush()
            return True
        return False


class AgentHeartbeatRepository(BaseRepository[AgentHeartbeat]):
    """AgentHeartbeat data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(AgentHeartbeat, db)

    async def get_latest(self, agent_id: str) -> Optional[AgentHeartbeat]:
        """Get the latest heartbeat for an agent."""
        result = await self.db.execute(
            select(AgentHeartbeat)
            .where(AgentHeartbeat.agent_id == agent_id)
            .order_by(desc(AgentHeartbeat.received_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_agent(
        self,
        agent_id: str,
        skip: int = 0,
        limit: int = 20,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
    ) -> tuple[Sequence[AgentHeartbeat], int]:
        """List heartbeats for an agent."""
        query = select(AgentHeartbeat).where(AgentHeartbeat.agent_id == agent_id)

        if start_time:
            query = query.where(AgentHeartbeat.received_at >= start_time)
        if end_time:
            query = query.where(AgentHeartbeat.received_at <= end_time)

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(desc(AgentHeartbeat.received_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total


# Helper for PostgreSQL conditional aggregation
def case(whens, else_=None):
    from sqlalchemy import case as sa_case
    return sa_case(whens, else_=else_)