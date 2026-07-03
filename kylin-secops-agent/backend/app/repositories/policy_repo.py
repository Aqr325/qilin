"""Policy repository."""

import uuid
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.policy import Policy, PolicyVersion, PolicyTarget
from app.repositories.base import BaseRepository


class PolicyRepository(BaseRepository[Policy]):
    """Policy data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(Policy, db)

    async def list_paginated(
        self,
        skip: int = 0,
        limit: int = 20,
        status: Optional[str] = None,
        policy_type: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> tuple[Sequence[Policy], int]:
        """List policies with filters."""
        query = select(Policy).where(Policy.is_deleted == False)

        if status:
            query = query.where(Policy.status == status)
        if policy_type:
            query = query.where(Policy.policy_type == policy_type)
        if keyword:
            query = query.where(
                or_(
                    Policy.name.ilike(f"%{keyword}%"),
                    Policy.description.ilike(f"%{keyword}%"),
                )
            )

        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.db.execute(count_query)).scalar() or 0

        query = query.order_by(desc(Policy.updated_at)).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total


class PolicyVersionRepository(BaseRepository[PolicyVersion]):
    """PolicyVersion data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(PolicyVersion, db)

    async def list_by_policy(self, policy_id: uuid.UUID) -> Sequence[PolicyVersion]:
        result = await self.db.execute(
            select(PolicyVersion)
            .where(PolicyVersion.policy_id == policy_id)
            .order_by(desc(PolicyVersion.version))
        )
        return result.scalars().all()

    async def get_version(
        self, policy_id: uuid.UUID, version: int
    ) -> Optional[PolicyVersion]:
        result = await self.db.execute(
            select(PolicyVersion).where(
                PolicyVersion.policy_id == policy_id,
                PolicyVersion.version == version,
            )
        )
        return result.scalar_one_or_none()


class PolicyTargetRepository(BaseRepository[PolicyTarget]):
    """PolicyTarget data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(PolicyTarget, db)

    async def list_by_policy(self, policy_id: uuid.UUID) -> Sequence[PolicyTarget]:
        result = await self.db.execute(
            select(PolicyTarget)
            .where(PolicyTarget.policy_id == policy_id)
        )
        return result.scalars().all()

    async def get_deploy_status(self, policy_id: uuid.UUID) -> Dict[str, Any]:
        result = await self.db.execute(
            select(
                PolicyTarget.status,
                func.count().label("count"),
            )
            .where(PolicyTarget.policy_id == policy_id)
            .group_by(PolicyTarget.status)
        )
        status_map = {row.status: row.count for row in result.all()}
        total = sum(status_map.values())
        return {
            "deployed": status_map.get("deployed", 0),
            "pending": status_map.get("pending", 0),
            "failed": status_map.get("failed", 0),
            "total": total,
        }