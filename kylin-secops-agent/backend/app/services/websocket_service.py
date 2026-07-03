"""WebSocket service: connection manager, Redis Pub/Sub bridge."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class WebSocketManager:
    """WebSocket connection manager with Redis Pub/Sub bridge."""

    def __init__(self):
        # Connection storage: conn_id -> WebSocket
        self._connections: Dict[str, WebSocket] = {}
        # Connection metadata: conn_id -> metadata
        self._metadata: Dict[str, Dict[str, Any]] = {}
        # Channel subscriptions: channel -> Set[conn_id]
        self._channels: Dict[str, Set[str]] = {}
        # User-channel mapping: user_id -> Set[channel]
        self._user_channels: Dict[str, Set[str]] = {}
        # Redis subscriber (lazy init)
        self._redis = None
        self._redis_pubsub = None
        self._redis_listener_task = None
        self._running = False

    async def connect(
        self,
        websocket: WebSocket,
        conn_id: str,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        roles: Optional[List[str]] = None,
    ) -> bool:
        """Accept a new WebSocket connection."""
        try:
            await websocket.accept()
            self._connections[conn_id] = websocket
            self._metadata[conn_id] = {
                "user_id": user_id,
                "username": username,
                "roles": roles or [],
                "connected_at": datetime.now(timezone.utc).isoformat(),
            }
            # Subscribe to role-appropriate channels
            if roles:
                if "admin" in roles:
                    await self.subscribe(conn_id, "alerts:*")
                    await self.subscribe(conn_id, "agents:*")
                    await self.subscribe(conn_id, "policies:*")
                    await self.subscribe(conn_id, "system:*")
                    await self.subscribe(conn_id, "ai:*")
                elif "operator" in roles:
                    await self.subscribe(conn_id, "alerts:*")
                    await self.subscribe(conn_id, "agents:status")
                    await self.subscribe(conn_id, "ai:*")
                elif "auditor" in roles:
                    await self.subscribe(conn_id, "alerts:*")
                else:
                    await self.subscribe(conn_id, "alerts:new")
            return True
        except Exception as e:
            logger.error(f"WebSocket accept failed: {e}")
            return False

    async def disconnect(self, conn_id: str):
        """Remove a connection and clean up subscriptions."""
        if conn_id in self._connections:
            try:
                await self._connections[conn_id].close()
            except Exception:
                pass
            del self._connections[conn_id]

        # Remove from all channels
        metadata = self._metadata.pop(conn_id, {})
        user_id = metadata.get("user_id")

        for channel in list(self._channels.keys()):
            self._channels[channel].discard(conn_id)
            if not self._channels[channel]:
                del self._channels[channel]

        if user_id and user_id in self._user_channels:
            del self._user_channels[user_id]

        logger.info(f"WebSocket disconnected: {conn_id}")

    async def subscribe(self, conn_id: str, channel: str):
        """Subscribe a connection to a channel."""
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(conn_id)

        metadata = self._metadata.get(conn_id, {})
        user_id = metadata.get("user_id")
        if user_id:
            if user_id not in self._user_channels:
                self._user_channels[user_id] = set()
            self._user_channels[user_id].add(channel)

    async def unsubscribe(self, conn_id: str, channel: str):
        """Unsubscribe a connection from a channel."""
        if channel in self._channels:
            self._channels[channel].discard(conn_id)
            if not self._channels[channel]:
                del self._channels[channel]

        metadata = self._metadata.get(conn_id, {})
        user_id = metadata.get("user_id")
        if user_id and user_id in self._user_channels:
            self._user_channels[user_id].discard(channel)

    async def send_to(self, conn_id: str, event_type: str, data: Any):
        """Send a message to a specific connection."""
        ws = self._connections.get(conn_id)
        if not ws:
            return
        try:
            message = json.dumps({
                "type": event_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            })
            await ws.send_text(message)
        except Exception as e:
            logger.warning(f"Send to {conn_id} failed: {e}")
            await self.disconnect(conn_id)

    async def broadcast(self, event_type: str, data: Any, channel: Optional[str] = None):
        """Broadcast a message to all connections matching a channel pattern."""
        message = json.dumps({
            "type": event_type,
            "channel": channel or event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data,
        })

        # Send to all connections if no channel specified
        if not channel:
            tasks = [ws.send_text(message) for ws in self._connections.values()]
            await asyncio.gather(*tasks, return_exceptions=True)
            return

        # Send to channel subscribers
        matched_connections: Set[str] = set()
        for ch_pattern, conns in self._channels.items():
            if self._channel_matches(ch_pattern, channel):
                matched_connections.update(conns)

        tasks = []
        for conn_id in matched_connections:
            ws = self._connections.get(conn_id)
            if ws:
                tasks.append(ws.send_text(message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast_to_channel(self, channel: str, event_type: str, data: Any):
        """Broadcast to a specific channel."""
        await self.broadcast(event_type, data, channel=channel)

    async def handle_client_message(self, conn_id: str, message_str: str):
        """Process incoming WebSocket message from client."""
        try:
            message = json.loads(message_str)
        except json.JSONDecodeError:
            await self.send_to(conn_id, "error", {"message": "Invalid JSON"})
            return

        msg_type = message.get("type")
        if msg_type == "ping":
            await self.send_to(conn_id, "pong", {
                "server_time": datetime.now(timezone.utc).isoformat(),
            })
        elif msg_type == "subscribe":
            channels = message.get("channels", [])
            for ch in channels:
                await self.subscribe(conn_id, ch)
            await self.send_to(conn_id, "subscribed", {
                "channels": channels,
                "ok": True,
            })
        elif msg_type == "unsubscribe":
            channels = message.get("channels", [])
            for ch in channels:
                await self.unsubscribe(conn_id, ch)
        elif msg_type == "alert.ack":
            logger.info(f"Alert ack from {conn_id}: {message.get('alert_id')}")

    def get_connection_count(self) -> int:
        """Get total active connection count."""
        return len(self._connections)

    def get_connections_for_user(self, user_id: str) -> List[str]:
        """Get all connection IDs for a user."""
        return [
            cid for cid, meta in self._metadata.items()
            if meta.get("user_id") == user_id
        ]

    def _channel_matches(self, pattern: str, channel: str) -> bool:
        """Check if a channel matches a pattern (supports wildcard *)."""
        if pattern == channel:
            return True
        if pattern.endswith(":*"):
            prefix = pattern[:-2]
            return channel.startswith(prefix)
        return False

    # ── Redis Pub/Sub Bridge ──

    async def start_redis_listener(self):
        """Start Redis Pub/Sub listener in background."""
        try:
            import redis.asyncio as aioredis
            from app.core.config import settings

            self._redis = aioredis.from_url(settings.REDIS_URL)
            self._redis_pubsub = self._redis.pubsub()

            # Subscribe to broadcast channels
            await self._redis_pubsub.subscribe(
                "ws:broadcast:alert:new",
                "ws:broadcast:alert:update",
                "ws:broadcast:agent:status",
                "ws:broadcast:policy:deploy",
                "ws:broadcast:system:announce",
            )

            self._running = True
            self._redis_listener_task = asyncio.create_task(self._redis_listen())
            logger.info("Redis Pub/Sub listener started")
        except Exception as e:
            logger.warning(f"Redis Pub/Sub not available: {e}")

    async def stop_redis_listener(self):
        """Stop Redis Pub/Sub listener."""
        self._running = False
        if self._redis_listener_task:
            self._redis_listener_task.cancel()
            try:
                await self._redis_listener_task
            except asyncio.CancelledError:
                pass
        if self._redis_pubsub:
            await self._redis_pubsub.close()
        if self._redis:
            try:
                await self._redis.close()
            except Exception:
                pass
        logger.info("Redis Pub/Sub listener stopped")

    async def _redis_listen(self):
        """Listen for Redis Pub/Sub messages and broadcast to WebSocket."""
        while self._running:
            try:
                message = await self._redis_pubsub.get_message(
                    timeout=1.0, ignore_subscribe_messages=True
                )
                if message and message.get("type") == "message":
                    channel = message["channel"].decode()
                    data = json.loads(message["data"])

                    # Map Redis channel to WS event type
                    event_map = {
                        "ws:broadcast:alert:new": ("alert.new", "alerts:new"),
                        "ws:broadcast:alert:update": ("alert.updated", "alerts:updates"),
                        "ws:broadcast:agent:status": ("agent.status", "agents:status"),
                        "ws:broadcast:policy:deploy": ("policy.deployed", "policies:ops"),
                        "ws:broadcast:system:announce": ("system.announcement", "system:all"),
                    }

                    if channel in event_map:
                        event_type, ws_channel = event_map[channel]
                        await self.broadcast(event_type, data, channel=ws_channel)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Redis listener error: {e}")
                await asyncio.sleep(1)

    async def publish_to_redis(self, channel: str, data: Any):
        """Publish a message to Redis Pub/Sub."""
        if hasattr(self, "_redis") and self._redis:
            await self._redis.publish(channel, json.dumps(data))


# Global WebSocket manager instance
ws_manager = WebSocketManager()