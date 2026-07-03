#!/usr/bin/env python3
"""
Kylin Security Operations Agent — Main entry point.

Launches all subsystems as asyncio tasks:
  - WebSocket client (connection, heartbeat, message routing)
  - Heartbeat collector (periodic resource acquisition)
  - Security event collector (process/net/file/log monitors)
  - Policy engine (event evaluation, offline mode, audit logging)
  - Remote ops channel (command execution, upgrade, hot-reload)

State machine:
  online → WS timeout 30s → offline (isolated execution) → reconnect → sync → online
"""

import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from src import __version__
from src.config import load_config, DATA_DIR, PID_FILE, CONFIG_DIR
from src.logger import get_logger, AgentLogger
from src.db import LocalDB
from src.ws_client import WsClient, MessageRouter
from src.heartbeat import HeartbeatCollector
from src.collector import SecurityCollector
from src.engine import PolicyEngine
from src.remote import CommandExecutor, PolicyHotReloader
from src.upgrade import AgentUpgrader

logger = get_logger("main")


class Agent:
    """Main agent orchestrator — manages all subsystems."""

    def __init__(self):
        self._config = load_config()
        self._stopping = False

        # Subsystems (initialized in setup)
        self._db: Optional[LocalDB] = None
        self._router: Optional[MessageRouter] = None
        self._ws: Optional[WsClient] = None
        self._heartbeat: Optional[HeartbeatCollector] = None
        self._collector: Optional[SecurityCollector] = None
        self._engine: Optional[PolicyEngine] = None
        self._executor: Optional[CommandExecutor] = None
        self._reloader: Optional[PolicyHotReloader] = None
        self._upgrader: Optional[AgentUpgrader] = None

        # Internal state
        self._offline_start_ts: Optional[float] = None
        self._tasks: list = []

    # ═══════════════════════════════════════════════════════════════════
    # Setup
    # ═══════════════════════════════════════════════════════════════════

    def setup(self):
        """Initialize all subsystems."""
        log_cfg = self._config.get("logging", default={})
        AgentLogger().setup(
            level=log_cfg.get("level", "INFO"),
            debug_console=log_cfg.get("debug_console", False),
        )
        logger.info("Kylin Security Ops Agent v%s starting...", __version__)

        # Create data directories
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Database
        self._db = LocalDB(DATA_DIR / "agent.db")
        self._db.open()

        # Message router
        self._router = MessageRouter()

        # WebSocket client
        self._ws = WsClient(self._config, self._router, self._on_state_change)
        self._ws.set_db(self._db)

        # Policy engine
        self._engine = PolicyEngine(
            db=self._db,
            on_alert=self._on_alert_triggered,
            on_sync_needed=self._on_sync_needed,
        )

        # Heartbeat collector
        self._heartbeat = HeartbeatCollector(
            config=self._config,
            on_heartbeat=self._on_heartbeat_data,
            on_alert=self._on_heartbeat_alert,
        )

        # Security collector
        self._collector = SecurityCollector(
            config=self._config,
            on_event=self._on_security_event,
        )

        # Command executor
        self._executor = CommandExecutor(on_result=self._on_command_result)

        # Policy hot-reloader
        self._reloader = PolicyHotReloader(
            engine=self._engine,
            db=self._db,
            ws_client=self._ws,
        )

        # Agent upgrader
        self._upgrader = AgentUpgrader(
            data_dir=DATA_DIR,
            on_progress=self._on_upgrade_progress,
        )

        # Register message handlers
        self._register_handlers()

        # Write PID file
        self._write_pid()

        logger.info("Agent setup complete")

    def _register_handlers(self):
        """Register WebSocket message type handlers."""
        self._router.register("policy_push", self._reloader.handle_policy_push)
        self._router.register("command", self._executor.handle_command_message)
        self._router.register("upgrade", self._upgrader.handle_upgrade_message)
        self._router.register("sync_response", self._handle_sync_response)

    # ═══════════════════════════════════════════════════════════════════
    # Run
    # ═══════════════════════════════════════════════════════════════════

    async def run(self):
        """Start all subsystems and wait for shutdown."""
        logger.info("Starting agent subsystems...")

        # Load current policy from SQLite
        policy = self._db.get_current_policy()
        if policy:
            ok, err = self._engine.load_policy(policy["content_yaml"])
            if ok:
                logger.info("Loaded policy v%d from local cache", policy["version"])
            else:
                logger.warning("Failed to load cached policy: %s", err)

        # Start tasks
        self._tasks = [
            asyncio.create_task(self._ws.connect(), name="ws"),
            asyncio.create_task(self._heartbeat.run(), name="heartbeat"),
            asyncio.create_task(self._collector.start(), name="collector"),
            asyncio.create_task(self._offline_monitor(), name="offline_monitor"),
        ]

        logger.info("All subsystems started (%d tasks)", len(self._tasks))

        # Wait for completion (or shutdown signal)
        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass
        finally:
            await self._shutdown()

    async def _shutdown(self):
        """Graceful shutdown of all subsystems."""
        logger.info("Shutting down agent...")
        self._stopping = True

        # Stop subsystems
        self._heartbeat.stop()

        # Cancel all tasks
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        # Close connections
        await self._ws.disconnect()
        self._db.close()

        # Remove PID file
        self._remove_pid()
        logger.info("Agent shutdown complete")

    # ═══════════════════════════════════════════════════════════════════
    # State management
    # ═══════════════════════════════════════════════════════════════════

    async def _on_state_change(self, old_state: str, new_state: str):
        """Handle WebSocket client state transitions."""
        logger.info("Agent state: %s → %s", old_state, new_state)

        if new_state == "offline" and old_state == "online":
            self._offline_start_ts = time.time()
            self._engine.set_state("offline")
            logger.info("Entered offline mode")

        elif new_state == "online" and old_state in ("offline", "syncing"):
            self._offline_start_ts = None
            self._engine.set_state("online")
            logger.info("Returned to online mode")

    async def _offline_monitor(self):
        """Periodically check offline status and manage buffer."""
        while not self._stopping:
            try:
                await asyncio.sleep(10)

                if self._ws.state == "offline":
                    # Check if we exceeded the offline timeout
                    if self._offline_start_ts:
                        elapsed = time.time() - self._offline_start_ts
                        if elapsed > 3600:  # 1 hour
                            logger.warning(
                                "Offline for %.0f minutes; audit buffer may be filling",
                                elapsed / 60,
                            )

                    # Flush audit logs if buffer is getting full
                    count = self._db.count_audit_logs()
                    if count > 9000:
                        logger.warning(
                            "Audit log buffer at %d/%d",
                            count, self._config.get("engine", "audit_log_max", default=10000),
                        )

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Offline monitor error: %s", exc)

    # ═══════════════════════════════════════════════════════════════════
    # Callbacks
    # ═══════════════════════════════════════════════════════════════════

    async def _on_heartbeat_data(self, payload: Dict[str, Any]):
        """Callback when heartbeat data is ready."""
        await self._ws.send(payload)

    async def _on_heartbeat_alert(self, payload: Dict[str, Any]):
        """Callback for immediate anomaly push."""
        await self._ws.send(payload)

    async def _on_security_event(self, event: Dict[str, Any]):
        """Callback when a security event is captured."""
        # Evaluate against policy engine (both online and offline)
        await self._engine.process_event(event)

        # Forward to platform (buffered if offline)
        if self._ws.is_online:
            await self._ws.send({
                "type": "event",
                "agent_id": self._config.agent_id,
                "events": [event],
            })
        else:
            # Log locally
            self._db.append_audit_log(
                action="event_collected",
                detail=f"type={event.get('type')}",
                result="buffered",
            )

    async def _on_alert_triggered(self, alert: Dict[str, Any]):
        """Callback when the policy engine fires an alert."""
        logger.warning("Alert: rule=%s severity=%s", alert.get("rule_id"), alert.get("severity"))
        # In online mode, forward to platform
        if self._ws.is_online:
            await self._ws.send({
                "type": "alert",
                "agent_id": self._config.agent_id,
                "data": alert,
            })

    async def _on_sync_needed(self):
        """Callback indicating sync is needed (triggered on policy mismatch)."""
        logger.info("Sync needed — will sync on next reconnect")

    async def _on_command_result(self, result: Dict[str, Any]):
        """Callback with command execution result."""
        result["type"] = "command_result"
        result["agent_id"] = self._config.agent_id
        await self._ws.send(result)

    async def _on_upgrade_progress(self, progress: Dict[str, Any]):
        """Callback with upgrade progress updates."""
        progress["agent_id"] = self._config.agent_id
        await self._ws.send(progress)

    async def _handle_sync_response(self, msg: Dict[str, Any]):
        """Handle sync_response from platform."""
        logger.info("Sync response received: policy_status=%s events_ack=%s",
                    msg.get("policy_status"), msg.get("events_ack"))

        # If platform says policy needs update, apply new one
        if msg.get("policy_status") == "needs_update":
            new_policy = msg.get("new_policy", {})
            if new_policy:
                await self._reloader.handle_policy_push(new_policy)

        # If events were acknowledged, clear local buffer
        if msg.get("events_ack"):
            self._db.clear_audit_logs()

    # ═══════════════════════════════════════════════════════════════════
    # PID file management
    # ═══════════════════════════════════════════════════════════════════

    def _write_pid(self):
        try:
            PID_FILE.write_text(str(os.getpid()))
        except (IOError, OSError) as exc:
            logger.warning("Cannot write PID file %s: %s", PID_FILE, exc)

    def _remove_pid(self):
        try:
            if PID_FILE.exists():
                PID_FILE.unlink()
        except (IOError, OSError) as exc:
            logger.warning("Cannot remove PID file %s: %s", PID_FILE, exc)


# ═════════════════════════════════════════════════════════════════════════
# Entry point
# ═════════════════════════════════════════════════════════════════════════

def main():
    agent = Agent()
    agent.setup()

    # Handle signals
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _signal_handler():
        logger.info("Received signal, shutting down...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    try:
        loop.add_signal_handler(signal.SIGTERM, _signal_handler)
        loop.add_signal_handler(signal.SIGINT, _signal_handler)
    except NotImplementedError:
        # Windows doesn't support add_signal_handler
        pass

    try:
        loop.run_until_complete(agent.run())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt")
    finally:
        # Cancel remaining tasks
        for task in asyncio.all_tasks(loop):
            task.cancel()
        loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
        loop.close()
        logger.info("Agent exited")


if __name__ == "__main__":
    main()
