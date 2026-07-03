"""
WebSocket client for Agent-platform communication.

Handles:
  - Connection management (connect, reconnect with exponential backoff)
  - Message routing (type-based dispatch)
  - Heartbeat ping/pong keep-alive
  - Offline buffering (local queue, batch replay on reconnect)
  - Sync protocol (sync_request/sync_response)

Protocol: JSON over wss (or ws for dev).
"""

import asyncio
import json
import time
from collections import deque
from typing import Any, Callable, Coroutine, Dict, Optional

import aiohttp

from src import __version__
from src.logger import get_logger

logger = get_logger("ws")

# Maximum offline buffer size
_MAX_BUFFER = 1000


class MessageRouter:
    """Routes incoming WebSocket messages by 'type' field."""

    def __init__(self):
        self._handlers: Dict[str, list] = {}

    def register(self, msg_type: str, handler: Callable[..., Coroutine]):
        """Register an async handler for a message type."""
        self._handlers.setdefault(msg_type, []).append(handler)

    async def dispatch(self, msg: Dict[str, Any]) -> None:
        """Dispatch a parsed message to registered handlers."""
        msg_type = msg.get("type", "")
        handlers = self._handlers.get(msg_type, [])
        if not handlers:
            logger.warning("No handler for message type: %s", msg_type)
            return
        for h in handlers:
            try:
                await h(msg)
            except Exception as exc:
                logger.exception("Handler %s failed for type %s: %s", h.__name__, msg_type, exc)


class WsClient:
    """WebSocket client with auto-reconnect and offline buffering.

    State machine:
      online → WS timeout 30s → offline → network restored → sync → online
    """

    def __init__(
        self,
        config,
        router: MessageRouter,
        on_state_change: Optional[Callable[[str, str], Coroutine]] = None,
    ):
        self._config = config
        self._router = router
        self._on_state_change = on_state_change

        # Connection
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._ws_url = config.ws_url
        self._token = config.get("platform", "token") or ""

        # Reconnect settings
        self._reconnect_min = config.get("websocket", "reconnect_min_delay") or 1
        self._reconnect_max = config.get("websocket", "reconnect_max_delay") or 60
        self._offline_timeout = config.get("websocket", "offline_timeout") or 30
        self._ping_interval = config.get("websocket", "ping_interval") or 15

        # State
        self._running = False
        self._state = "initializing"  # online | offline | syncing | initializing
        self._last_ws_ts = 0.0        # last successful WS message timestamp
        self._offline_buffer: deque = deque(maxlen=_MAX_BUFFER)

        # Sync status
        self._db = None  # set via set_db()

        # Authentication headers
        self._headers = {}
        if self._token:
            self._headers["Authorization"] = f"Bearer {self._token}"

    def set_db(self, db):
        """Inject local DB reference for policy version advertisement."""
        self._db = db

    # ═══════════════════════════════════════════════════════════════════
    # State management
    # ═══════════════════════════════════════════════════════════════════

    async def _set_state(self, new_state: str):
        old = self._state
        if old == new_state:
            return
        self._state = new_state
        logger.info("State transition: %s → %s", old, new_state)
        if self._on_state_change:
            try:
                await self._on_state_change(old, new_state)
            except Exception as exc:
                logger.exception("State change handler error: %s", exc)

    @property
    def state(self) -> str:
        return self._state

    @property
    def is_online(self) -> bool:
        return self._state == "online"

    # ═══════════════════════════════════════════════════════════════════
    # Connection lifecycle
    # ═══════════════════════════════════════════════════════════════════

    async def connect(self):
        """Establish WebSocket connection and start the read loop."""
        self._running = True
        while self._running:
            try:
                await self._do_connect()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.warning("Connection error: %s; reconnecting...", exc)
                await self._reconnect_wait()

    async def _do_connect(self):
        """Single connect attempt."""
        if self._session is None:
            connector = aiohttp.TCPConnector(force_close=True)
            self._session = aiohttp.ClientSession(
                connector=connector,
                headers=self._headers,
            )

        logger.info("Connecting to %s ...", self._ws_url)
        self._ws = await self._session.ws_connect(
            self._ws_url,
            heartbeat=self._ping_interval,
            ssl=self._config.get("platform", "use_ssl", default=True),
        )
        logger.info("WebSocket connected to %s", self._ws_url)
        self._last_ws_ts = time.time()
        await self._set_state("online")

        # If we have buffered messages, replay them
        await self._flush_offline_buffer()

        # Run sync protocol
        await self._perform_sync()

        # Message read loop
        await self._read_loop()

    async def _read_loop(self):
        """Read incoming messages from WebSocket."""
        async for msg in self._ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                self._last_ws_ts = time.time()
                try:
                    data = json.loads(msg.data)
                    await self._router.dispatch(data)
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON received: %s", msg.data[:200])
                except Exception as exc:
                    logger.exception("Message dispatch error: %s", exc)

            elif msg.type == aiohttp.WSMsgType.CLOSED:
                logger.info("WebSocket closed by server")
                break
            elif msg.type == aiohttp.WSMsgType.ERROR:
                logger.error("WebSocket error: %s", self._ws.exception())
                break
            elif msg.type == aiohttp.WSMsgType.PONG:
                self._last_ws_ts = time.time()

    async def _reconnect_wait(self):
        """Exponential backoff wait before reconnect."""
        await self._set_state("offline")

        # Clean up old WS
        if self._ws and not self._ws.closed:
            await self._ws.close()
            self._ws = None

        # Exponential backoff
        delay = self._reconnect_min
        while self._running:
            await asyncio.sleep(delay)
            if delay >= self._reconnect_max:
                break
            delay = min(delay * 2, self._reconnect_max)

    async def disconnect(self):
        """Graceful disconnect."""
        self._running = False
        if self._ws and not self._ws.closed:
            await self._ws.close()
            self._ws = None
        if self._session:
            await self._session.close()
            self._session = None

    # ═══════════════════════════════════════════════════════════════════
    # Sending messages
    # ═══════════════════════════════════════════════════════════════════

    async def send(self, payload: Dict[str, Any]) -> bool:
        """Send a JSON message. Buffers if offline. Returns True if sent."""
        if self._ws and not self._ws.closed and self._state == "online":
            try:
                await self._ws.send_json(payload)
                return True
            except Exception as exc:
                logger.warning("Send failed: %s; buffering", exc)

        # Buffer for offline replay
        self._offline_buffer.append(payload)
        return False

    async def send_raw(self, text: str):
        """Send raw text (e.g. pre-serialized JSON)."""
        if self._ws and not self._ws.closed and self._state == "online":
            try:
                await self._ws.send_str(text)
            except Exception as exc:
                logger.warning("Send raw failed: %s", exc)

    # ═══════════════════════════════════════════════════════════════════
    # Offline buffer management
    # ═══════════════════════════════════════════════════════════════════

    async def _flush_offline_buffer(self):
        """Replay buffered messages on reconnect."""
        if not self._offline_buffer:
            return
        count = len(self._offline_buffer)
        logger.info("Flushing %d buffered messages...", count)

        # Send as batch if possible
        batch = []
        while self._offline_buffer:
            msg = self._offline_buffer.popleft()
            batch.append(msg)
            if len(batch) >= 50:
                await self._send_batch(batch)
                batch = []
        if batch:
            await self._send_batch(batch)

        logger.info("Flushed %d buffered messages", count)

    async def _send_batch(self, messages: list):
        """Send a batch of messages."""
        for m in messages:
            try:
                await self._ws.send_json(m)
            except Exception:
                # If send fails, push back to front of buffer
                for m_rev in reversed(messages):
                    self._offline_buffer.appendleft(m_rev)
                break

    # ═══════════════════════════════════════════════════════════════════
    # Sync protocol
    # ═══════════════════════════════════════════════════════════════════

    async def _perform_sync(self):
        """Execute sync_request/sync_response protocol on reconnect."""
        await self._set_state("syncing")

        if self._db is None:
            await self._set_state("online")
            return

        local_version, local_checksum = self._db.get_policy_version_checksum()
        offline_count = self._db.count_audit_logs()

        sync_req = {
            "type": "sync_request",
            "agent_id": self._config.agent_id,
            "local_policy_version": local_version or 0,
            "local_policy_checksum": local_checksum or "",
            "offline_duration_sec": 0,  # Will be estimated
            "offline_events_count": offline_count,
        }

        try:
            await self._ws.send_json(sync_req)
            # Wait for sync_response — the router will handle it
            logger.info("Sync request sent (policy v%s, %d offline events)",
                        local_version, offline_count)
        except Exception as exc:
            logger.error("Sync request failed: %s", exc)
        finally:
            await self._set_state("online")

    # ═══════════════════════════════════════════════════════════════════
    # Offline timeout detection (called from main loop)
    # ═══════════════════════════════════════════════════════════════════

    async def check_offline_timeout(self):
        """Periodically check if WS has timed out (called externally)."""
        if self._state != "online":
            return
        now = time.time()
        if now - self._last_ws_ts > self._offline_timeout:
            logger.warning("WebSocket timeout (>%ds); switching to offline mode",
                           self._offline_timeout)
            await self._set_state("offline")
            # Force a reconnect by closing the current WS
            if self._ws and not self._ws.closed:
                await self._ws.close()
