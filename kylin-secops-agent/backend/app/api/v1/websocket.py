"""WebSocket route for real-time communication."""

import json
import uuid
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_optional
from app.core.database import get_db
from app.services.websocket_service import ws_manager

router = APIRouter(tags=["WebSocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for dashboard/management clients.

    URL: /api/v1/ws?token={jwt_token}
    """
    token = websocket.query_params.get("token")
    conn_id = str(uuid.uuid4())

    # Authenticate via token
    user_info = {"user_id": None, "username": "anonymous", "roles": ["readonly"]}
    if token:
        try:
            from app.core.security import decode_token
            payload = decode_token(token)
            user_info = {
                "user_id": payload.get("sub"),
                "username": payload.get("username", "unknown"),
                "roles": payload.get("roles", ["readonly"]),
            }
        except Exception:
            pass

    connected = await ws_manager.connect(
        websocket, conn_id,
        user_id=user_info["user_id"],
        username=user_info["username"],
        roles=user_info["roles"],
    )

    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.handle_client_message(conn_id, data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        pass
    finally:
        await ws_manager.disconnect(conn_id)


@router.websocket("/ws/agent/{agent_id}")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for Agent connections.

    URL: /api/v1/ws/agent/{agent_id}
    """
    conn_id = f"agent:{agent_id}"
    connected = await ws_manager.connect(
        websocket, conn_id,
        username=agent_id,
        roles=["agent"],
    )

    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.handle_client_message(conn_id, data)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(conn_id)


@router.websocket("/ws/dashboard/{user_id}")
async def dashboard_websocket(websocket: WebSocket, user_id: str):
    """WebSocket endpoint for dashboard real-time data.

    URL: /api/v1/ws/dashboard/{user_id}
    """
    conn_id = f"dashboard:{user_id}:{uuid.uuid4()}"
    connected = await ws_manager.connect(
        websocket, conn_id,
        user_id=user_id,
        roles=["operator"],
    )

    if not connected:
        return

    try:
        while True:
            data = await websocket.receive_text()
            await ws_manager.handle_client_message(conn_id, data)
    except WebSocketDisconnect:
        pass
    finally:
        await ws_manager.disconnect(conn_id)