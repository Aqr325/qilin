"""
Agent configuration module.
Loads config.yaml from /etc/kylin-secops-agent/config.yaml with sensible defaults.
"""

import os
import platform
import socket
import yaml

from pathlib import Path
from typing import Optional


# ── System directory constants ────────────────────────────────────────────
CONFIG_DIR = Path("/etc/kylin-secops-agent")
DATA_DIR = Path("/var/lib/kylin-secops-agent")
LOG_DIR = Path("/var/log/kylin-secops-agent")
PID_FILE = Path("/var/run/kylin-secops-agent.pid")

CONFIG_FILE = CONFIG_DIR / "config.yaml"

# ── Default configuration ─────────────────────────────────────────────────
DEFAULT_CONFIG = {
    # Platform connection
    "platform": {
        "host": "secops.company.com",
        "port": 443,
        "use_ssl": True,
        "ws_path": "/api/v1/ws/agent",
        "token": "",
    },

    # Heartbeat
    "heartbeat": {
        "interval_min": 5,
        "interval_max": 12,
        "cpu_threshold": 90.0,
        "disk_threshold": 5.0,
    },

    # WebSocket
    "websocket": {
        "ping_interval": 15,
        "reconnect_min_delay": 1,
        "reconnect_max_delay": 60,
        "offline_timeout": 30,
    },

    # Collection
    "collector": {
        "enabled": True,
        "process_monitor": True,
        "network_monitor": True,
        "file_monitor": True,
        "log_monitor": True,
        "proc_scan_interval": 10,
        "net_scan_interval": 30,
        "file_watch_paths": [
            "/etc/passwd",
            "/etc/shadow",
            "/etc/ssh/sshd_config",
            "/etc/cron.allow",
            "/etc/cron.deny",
            "/etc/sudoers",
            "/etc/hosts.allow",
            "/etc/hosts.deny",
        ],
        "log_files": [
            "/var/log/secure",
            "/var/log/messages",
            "/var/log/audit/audit.log",
        ],
    },

    # Engine
    "engine": {
        "enabled": True,
        "audit_log_max": 10000,
        "offline_buffer_max": 1000,
    },

    # Logging
    "logging": {
        "level": "INFO",
        "debug_console": False,
        "max_bytes": 10485760,       # 10 MB
        "backup_count": 30,
    },

    # Agent identity
    "agent": {
        "id": "",
        "version": "",
    },
}


def _resolve_agent_id() -> str:
    """Auto-detect agent ID from hostname + a short suffix."""
    hostname = socket.gethostname()
    return f"kylin-{hostname}"


class AgentConfig:
    """Immutable config wrapper with attribute-style access."""

    def __init__(self, raw: dict):
        self._raw = raw

    def __getattr__(self, key: str):
        if key.startswith("_"):
            return super().__getattribute__(key)
        try:
            return self._raw[key]
        except KeyError:
            raise AttributeError(f"config has no key {key!r}")

    def get(self, *path: str, default=None):
        """Deep access: cfg.get('platform', 'host')"""
        val = self._raw
        for p in path:
            if isinstance(val, dict):
                val = val.get(p)
                if val is None:
                    return default
            else:
                return default
        return val

    @property
    def agent_id(self) -> str:
        return self._raw.get("agent", {}).get("id") or _resolve_agent_id()

    @property
    def ws_url(self) -> str:
        plat = self._raw.get("platform", {})
        scheme = "wss" if plat.get("use_ssl", True) else "ws"
        host = plat.get("host", "secops.company.com")
        port = plat.get("port", 443)
        path = plat.get("ws_path", "/api/v1/ws/agent")
        if (scheme == "wss" and port == 443) or (scheme == "ws" and port == 80):
            return f"{scheme}://{host}{path}/{self.agent_id}"
        return f"{scheme}://{host}:{port}{path}/{self.agent_id}"


def load_config(path: Optional[Path] = None) -> AgentConfig:
    """Load YAML config from path, merge with defaults."""
    cfg_path = path or CONFIG_FILE

    merged = DEFAULT_CONFIG.copy()

    if cfg_path.exists():
        with open(cfg_path, "r") as fh:
            user_cfg = yaml.safe_load(fh) or {}
        _deep_merge(merged, user_cfg)

    # Inject agent identity
    merged.setdefault("agent", {})
    if not merged["agent"].get("id"):
        merged["agent"]["id"] = _resolve_agent_id()
    if not merged["agent"].get("version"):
        from src import __version__
        merged["agent"]["version"] = __version__

    return AgentConfig(merged)


def _deep_merge(base: dict, overrides: dict) -> None:
    """Recursively merge overrides into base (in-place)."""
    for key, val in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val
