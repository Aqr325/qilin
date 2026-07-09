"""User, Role, Permission models."""

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, SoftDeleteMixin, TimestampMixin
from app.models.types import UUID, INET


# ── Association Tables ──

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("granted_by", String(36), ForeignKey("users.id"), nullable=True),
    Column("granted_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", String(36), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", String(36), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

# ── Permission ──

class Permission(Base, TimestampMixin):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=role_permissions, back_populates="permissions",
        foreign_keys=[role_permissions.c.permission_id, role_permissions.c.role_id]
    )

    def __repr__(self):
        return f"<Permission {self.code}>"


# ── Role ──

class Role(Base, TimestampMixin):
    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, server_default="0", default=False)

    users: Mapped[List["User"]] = relationship(
        "User", secondary=user_roles, back_populates="roles", lazy="select",
        foreign_keys=[user_roles.c.role_id, user_roles.c.user_id]
    )
    permissions: Mapped[List["Permission"]] = relationship(
        "Permission", secondary=role_permissions, back_populates="roles", lazy="selectin",
        foreign_keys=[role_permissions.c.role_id, role_permissions.c.permission_id]
    )

    def __repr__(self):
        return f"<Role {self.name}>"


# ── User ──

class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="1", default=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, server_default="0", default=False)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    login_attempts: Mapped[int] = mapped_column(Integer, server_default="0", default=0)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_ip: Mapped[Optional[str]] = mapped_column(INET, nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, server_default="0", default=False)
    mfa_secret: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    roles: Mapped[List["Role"]] = relationship(
        "Role", secondary=user_roles, back_populates="users", lazy="selectin",
        foreign_keys=[user_roles.c.user_id, user_roles.c.role_id]
    )

    @property
    def role_list(self) -> List[dict]:
        return [{"id": str(r.id), "name": r.name, "display_name": r.display_name} for r in self.roles]

    @property
    def permission_list(self) -> List[str]:
        perms = set()
        for role in self.roles:
            for perm in role.permissions:
                perms.add(perm.code)
        return sorted(list(perms))

    def __repr__(self):
        return f"<User {self.username}>"