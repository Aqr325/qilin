"""API layer dependencies: current user, pagination, etc."""

import uuid
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Query, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User, Role, Permission


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
    x_agent_token: Optional[str] = Header(None, alias="X-Agent-Token"),
) -> dict:
    """Get current authenticated user from JWT token."""
    if x_agent_token:
        # Agent token authentication
        return {"is_agent": True, "agent_id": "agent", "username": "agent"}

    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization scheme",
        )

    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired or invalid",
        )

    # Fetch user with roles and permissions
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles).selectinload(Role.permissions))
        .where(User.id == uuid.UUID(user_id), User.is_deleted == False)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    return {
        "id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "email": user.email,
        "roles": user.role_list,
        "permissions": user.permission_list,
    }


async def get_current_user_optional(
    request: Request,
    db: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """Optional authentication - returns None if not authenticated."""
    if not authorization:
        return None
    try:
        return await get_current_user(request, db, authorization)
    except HTTPException:
        return None


def get_pagination(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> dict:
    """Get pagination parameters."""
    return {"page": page, "size": size}


def get_request_id(request: Request) -> Optional[str]:
    """Get request ID from request state."""
    return getattr(request.state, "request_id", None)