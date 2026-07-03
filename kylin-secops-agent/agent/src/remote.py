"""
Remote operations channel.

Handles commands received from the platform via WebSocket:
  - Remote command execution (whitelisted commands only)
  - Policy hot-reload
  - High-risk command blocking

All commands are logged to the audit trail.
"""

import asyncio
import subprocess
import shlex
from typing import Any, Callable, Coroutine, Dict, List, Optional

from src.logger import get_logger

logger = get_logger("remote")

# ── Whitelisted commands ──────────────────────────────────────────────────
_WHITELIST_COMMANDS = {
    "systemctl", "df", "ps", "journalctl", "top", "free",
    "uptime", "who", "last", "netstat", "ss", "ip",
    "lsblk", "fdisk", "mount", "cat", "head", "tail",
    "grep", "find", "du", "ls", "echo",
}

# ── High-risk command patterns (blocked unconditionally) ──────────────────
_HIGH_RISK_COMMANDS = {
    "rm -rf /", "dd", "mkfs", "mkfs.ext4", "mkfs.xfs",
    "fdisk /dev/[sh]d[a-z]", "mke2fs", "format",
    ":(){ :|:& };:",  # fork bomb
}

# Max output size (10 KB)
_MAX_OUTPUT = 10 * 1024

# Command timeout
_CMD_TIMEOUT = 30


class CommandExecutor:
    """Sandboxed command executor with whitelist and high-risk blocking."""

    def __init__(self, on_result: Optional[Callable[..., Coroutine]] = None):
        self._on_result = on_result

    @staticmethod
    def _is_whitelisted(command: str) -> bool:
        """Check if the base command is in the whitelist."""
        parts = shlex.split(command)
        if not parts:
            return False
        base = parts[0]
        # Allow full paths like /usr/bin/systemctl
        base_name = base.split("/")[-1] if "/" in base else base
        return base_name in _WHITELIST_COMMANDS

    @staticmethod
    def _is_high_risk(command: str) -> bool:
        """Check if the command matches any high-risk pattern."""
        cmd_lower = command.lower().strip()
        for risk in _HIGH_RISK_COMMANDS:
            if cmd_lower.startswith(risk):
                return True
        return False

    async def execute(
        self,
        command: str,
        command_id: str = "",
    ) -> Dict[str, Any]:
        """Execute a command in a sandboxed subprocess.

        Returns:
            Dict with status, output, and error details.
        """
        if self._is_high_risk(command):
            logger.warning("Blocked high-risk command: %s", command)
            return {
                "command_id": command_id,
                "status": "rejected",
                "error": "High-risk command blocked",
                "output": "",
            }

        if not self._is_whitelisted(command):
            logger.warning("Blocked non-whitelist command: %s", command)
            return {
                "command_id": command_id,
                "status": "rejected",
                "error": f"Command not in whitelist: {command.split()[0]}",
                "output": "",
            }

        logger.info("Executing command: %s", command)
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=_CMD_TIMEOUT,
            )

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=_CMD_TIMEOUT
            )

            output = stdout.decode("utf-8", errors="replace")[: _MAX_OUTPUT]
            error = stderr.decode("utf-8", errors="replace")[: _MAX_OUTPUT]

            result = {
                "command_id": command_id,
                "status": "ok" if proc.returncode == 0 else "error",
                "returncode": proc.returncode,
                "output": output,
                "error": error,
            }

            logger.info("Command %s completed (rc=%d)", command_id, proc.returncode)
            return result

        except asyncio.TimeoutError:
            logger.warning("Command timed out after %ds: %s", _CMD_TIMEOUT, command)
            return {
                "command_id": command_id,
                "status": "timeout",
                "error": f"Command timed out after {_CMD_TIMEOUT}s",
                "output": "",
            }
        except FileNotFoundError:
            logger.warning("Command not found: %s", command)
            return {
                "command_id": command_id,
                "status": "error",
                "error": f"Command not found: {command}",
                "output": "",
            }
        except Exception as exc:
            logger.exception("Command execution error: %s", exc)
            return {
                "command_id": command_id,
                "status": "error",
                "error": str(exc),
                "output": "",
            }

    async def handle_command_message(self, msg: Dict[str, Any]):
        """Handle an incoming 'command' WebSocket message.

        Expected format:
            {"type": "command", "command_id": "...", "action": "exec", "command": "df -h"}
        """
        command_id = msg.get("command_id", "")
        command = msg.get("command", "")
        action = msg.get("action", "")

        if action != "exec" or not command:
            logger.warning("Invalid command message: %s", msg)
            return

        result = await self.execute(command, command_id)
        if self._on_result:
            await self._on_result(result)


class PolicyHotReloader:
    """Handles policy hot-reload from Redis Stream notifications."""

    def __init__(self, engine, db, ws_client):
        self._engine = engine
        self._db = db
        self._ws_client = ws_client

    async def handle_policy_push(self, msg: Dict[str, Any]):
        """Handle incoming policy_push message.

        Expected format:
            {"type": "policy_push", "version": 6, "content": "...", "checksum": "sha256:..."}
        """
        version = msg.get("version", 0)
        content = msg.get("content", "")
        checksum = msg.get("checksum", "")

        if not content or not checksum:
            logger.warning("Invalid policy push message")
            return

        ok = await self._engine.apply_policy_push(version, content, checksum)
        if ok:
            # Send policy_ack
            ack = {
                "type": "policy_ack",
                "version": version,
                "checksum": checksum,
            }
            await self._ws_client.send(ack)
            logger.info("Policy v%d acknowledged", version)
        else:
            logger.error("Policy v%d rejected", version)
