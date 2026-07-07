"""WebSocket route for real-time communication."""

import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.services.websocket_service import ws_manager

router = APIRouter(tags=["WebSocket"])


async def _authenticate_websocket_token(
    token: str | None,
    expected_id: str | None = None,
    id_field: str = "sub",
):
    """Authenticate a WebSocket connection via JWT token.

    Args:
        token: The JWT token string from query params.
        expected_id: If provided, the token's subject/agent_id must match this value.
        id_field: The JWT claim field to check against expected_id ("sub" or "agent_id").

    Returns:
        dict with user_info on success.

    Raises:
        WebSocketAuthenticationError: if authentication fails.
    """
    if not token:
        raise Exception("Missing authentication")

    try:
        payload = decode_token(token)
    except Exception:
        raise Exception("Invalid token")

    token_id = payload.get(id_field)
    if not token_id:
        raise Exception(f"Token missing required '{id_field}' claim")

    if expected_id and str(token_id) != expected_id:
        raise Exception(f"Token identity mismatch: expected {expected_id}, got {token_id}")

    return {
        "user_id": payload.get("sub"),
        "username": payload.get("username", "unknown"),
        "roles": payload.get("roles", ["readonly"]),
    }


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for dashboard/management clients.

    URL: /api/v1/ws?token={jwt_token}
    Authentication: JWT token required via ?token= query param.
    Connections without a valid token are rejected.
    """
    token = websocket.query_params.get("token")

    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Missing authentication")
        return

    try:
        user_info = _authenticate_websocket_token(token)
    except Exception as e:
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Invalid authentication: {e}")
        return

    conn_id = str(uuid.uuid4())

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
    except Exception:
        pass
    finally:
        await ws_manager.disconnect(conn_id)


@router.websocket("/ws/agent/{agent_id}")
async def agent_websocket(websocket: WebSocket, agent_id: str):
    """WebSocket endpoint for Agent connections.

    URL: /api/v1/ws/agent/{agent_id}?token={jwt_token}
    Authentication: JWT token required via ?token= query param.
    The token's agent_id claim must match the URL's {agent_id} path parameter.
    """
    token = websocket.query_params.get("token")

    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Missing authentication")
        return

    try:
        user_info = _authenticate_websocket_token(token, expected_id=agent_id, id_field="agent_id")
    except Exception as e:
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Invalid authentication: {e}")
        return

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

    URL: /api/v1/ws/dashboard/{user_id}?token={jwt_token}
    Authentication: JWT token required via ?token= query param.
    The token's sub claim must match the URL's {user_id} path parameter.
    """
    token = websocket.query_params.get("token")

    if not token:
        await websocket.accept()
        await websocket.close(code=1008, reason="Missing authentication")
        return

    try:
        user_info = _authenticate_websocket_token(token, expected_id=user_id, id_field="sub")
    except Exception as e:
        await websocket.accept()
        await websocket.close(code=1008, reason=f"Invalid authentication: {e}")
        return

    conn_id = f"dashboard:{user_id}:{uuid.uuid4()}"
    connected = await ws_manager.connect(
        websocket, conn_id,
        user_id=user_info["user_id"],
        roles=user_info.get("roles", ["operator"]),
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