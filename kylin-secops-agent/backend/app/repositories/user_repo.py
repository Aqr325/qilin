"""User repository."""

import uuid
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import User, Role, Permission
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """User data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(User, db)

    async def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username with roles and permissions."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles).selectinload(Role.permissions))
            .where(User.username == username, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(
            select(User).where(User.email == email, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def get_with_roles(self, user_id: uuid.UUID) -> Optional[User]:
        """Get user with roles loaded."""
        result = await self.db.execute(
            select(User)
            .options(selectinload(User.roles))
            .where(User.id == user_id, User.is_deleted == False)
        )
        return result.scalar_one_or_none()

    async def reset_login_attempts(self, user_id: uuid.UUID):
        """Reset login attempts counter."""
        user = await self.get(user_id)
        if user:
            user.login_attempts = 0
            user.is_locked = False
            user.locked_until = None
            await self.db.flush()

    async def increment_login_attempts(self, user_id: uuid.UUID):
        """Increment login attempts and lock if needed."""
        from app.core.config import settings

        user = await self.get(user_id)
        if user:
            user.login_attempts += 1
            if user.login_attempts >= settings.MAX_LOGIN_ATTEMPTS:
                from datetime import datetime, timezone, timedelta
                user.is_locked = True
                user.locked_until = datetime.now(timezone.utc) + timedelta(
                    minutes=settings.LOCKOUT_DURATION_MINUTES
                )
            await self.db.flush()

    async def update_last_login(self, user_id: uuid.UUID, ip_address: Optional[str] = None):
        """Update last login info."""
        from datetime import datetime, timezone

        user = await self.get(user_id)
        if user:
            user.last_login_at = datetime.now(timezone.utc)
            user.last_login_ip = ip_address
            user.login_attempts = 0
            await self.db.flush()


class RoleRepository(BaseRepository[Role]):
    """Role data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(Role, db)

    async def get_by_name(self, name: str) -> Optional[Role]:
        result = await self.db.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def get_with_permissions(self, role_id: uuid.UUID) -> Optional[Role]:
        result = await self.db.execute(
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id == role_id)
        )
        return result.scalar_one_or_none()

    async def list_all(self) -> List[Role]:
        result = await self.db.execute(
            select(Role).options(selectinload(Role.permissions))
        )
        return list(result.scalars().all())


class PermissionRepository(BaseRepository[Permission]):
    """Permission data access."""

    def __init__(self, db: AsyncSession):
        super().__init__(Permission, db)

    async def get_by_code(self, code: str) -> Optional[Permission]:
        result = await self.db.execute(
            select(Permission).where(Permission.code == code)
        )
        return result.scalar_one_or_none()

    async def list_by_module(self, module: str) -> List[Permission]:
        result = await self.db.execute(
            select(Permission).where(Permission.module == module)
        )
        return list(result.scalars().all())