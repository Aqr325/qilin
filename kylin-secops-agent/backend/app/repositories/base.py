"""Base CRUD repository with common database operations."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Generic, List, Optional, Sequence, Type, TypeVar

from sqlalchemy import func, select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Base repository with common CRUD operations."""

    def __init__(self, model: Type[ModelType], db: AsyncSession):
        self.model = model
        self.db = db

    async def create(self, **kwargs) -> ModelType:
        """Create a new record."""
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()
        return instance

    async def get(self, id: Any) -> Optional[ModelType]:
        """Get a record by primary key."""
        result = await self.db.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_by_field(self, field: str, value: Any) -> Optional[ModelType]:
        """Get a record by a specific field."""
        column = getattr(self.model, field, None)
        if column is None:
            raise ValueError(f"Field {field} does not exist on {self.model.__name__}")
        result = await self.db.execute(
            select(self.model).where(column == value)
        )
        return result.scalar_one_or_none()

    async def get_multi(
        self,
        skip: int = 0,
        limit: int = 20,
        order_by: Optional[str] = None,
        order_desc: bool = True,
        filters: Optional[Dict[str, Any]] = None,
    ) -> tuple[Sequence[ModelType], int]:
        """Get multiple records with pagination."""
        query = select(self.model)

        if filters:
            for field, value in filters.items():
                column = getattr(self.model, field, None)
                if column is not None:
                    if isinstance(value, list):
                        query = query.where(column.in_(value))
                    else:
                        query = query.where(column == value)

        # Count
        count_query = select(func.count()).select_from(query.subquery())
        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        # Order
        if order_by:
            column = getattr(self.model, order_by, None)
            if column is not None:
                query = query.order_by(column.desc() if order_desc else column.asc())

        query = query.offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all(), total

    async def update(self, id: Any, **kwargs) -> Optional[ModelType]:
        """Update a record by primary key."""
        instance = await self.get(id)
        if not instance:
            return None
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        await self.db.flush()
        return instance

    async def soft_delete(self, id: Any) -> bool:
        """Soft delete a record."""
        instance = await self.get(id)
        if not instance or getattr(instance, "is_deleted", False):
            return False
        instance.is_deleted = True  # type: ignore
        instance.deleted_at = datetime.now(timezone.utc)  # type: ignore
        await self.db.flush()
        return True

    async def hard_delete(self, id: Any) -> bool:
        """Hard delete a record."""
        instance = await self.get(id)
        if not instance:
            return False
        await self.db.delete(instance)
        await self.db.flush()
        return True

    async def exists(self, **filters) -> bool:
        """Check if a record exists with given filters."""
        query = select(self.model)
        for field, value in filters.items():
            column = getattr(self.model, field, None)
            if column is not None:
                query = query.where(column == value)
        result = await self.db.execute(query.limit(1))
        return result.scalar_one_or_none() is not None

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """Count records with optional filters."""
        query = select(func.count()).select_from(self.model)
        if filters:
            for field, value in filters.items():
                column = getattr(self.model, field, None)
                if column is not None:
                    query = query.where(column == value)
        result = await self.db.execute(query)
        return result.scalar() or 0

    async def bulk_create(self, items: List[Dict[str, Any]]) -> List[ModelType]:
        """Create multiple records in bulk."""
        instances = [self.model(**item) for item in items]
        self.db.add_all(instances)
        await self.db.flush()
        return instances