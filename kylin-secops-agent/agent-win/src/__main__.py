# -*- coding: utf-8 -*-
"""
Kylin SecOps Agent for Windows — lightweight agent runner.

Usage:
    python -m src main           # normal run
    python -m src run-once       # single heartbeat for testing

Depends: psutil, requests, pyyaml (all bundled via PyInstaller).
"""

import asyncio
import json
import logging
import os
import platform
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

import psutil

try:
    import requests
except ImportError:
    print("ERROR: 'requests' library is required. Install: pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    yaml = None

# ── Paths ──────────────────────────────────────────────────────────────────
# When running from PyInstaller: _MEIPASS → bundled; resources → deployment
if getattr(sys, "frozen", False):
    _base_dir = Path(os.environ.get("KYLIN_AGENT_RESOURCES", Path(sys.executable).parent / "resources"))
else:
    _base_dir = Path(__file__).resolve().parent.parent

CONFIG_PATH = _base_dir / "config.json"
LOG_PATH = _base_dir / "logs" / "agent.log"

# ── Logging ────────────────────────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_PATH), encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("kylin-agent")

# ── Config ─────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "backend_url": "http://127.0.0.1:8000",
    "agent_bootstrap_token": "kylin-agent-bootstrap-2026",
    "heartbeat_interval": 10,
    "agent_id_prefix": "kylin-win",
}


def load_config() -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, encoding="utf-8") as f:
                user = json.load(f)
            # Merge top-level keys that matter
            for k in DEFAULT_CONFIG:
                if k in user:
                    cfg[k] = user[k]
        except Exception as e:
            logger.warning("Failed to load config.json: %s", e)
    return cfg


# ── System metrics ─────────────────────────────────────────────────────────
def collect_cpu() -> Dict[str, Any]:
    # 非阻塞采集：interval=None 获取瞬时 CPU%（与上一次调用对比）
    # 在心跳场景下无需 0.5s 阻塞采样，瞬时值足够
    return {
        "usage": psutil.cpu_percent(interval=None),
        "count": psutil.cpu_count(logical=True),
    }


def collect_memory() -> Dict[str, Any]:
    mem = psutil.virtual_memory()
    return {
        "total": mem.total,
        "total_mb": round(mem.total / (1024 * 1024), 1),
        "used_mb": round(mem.used / (1024 * 1024), 1),
        "percent": round(mem.percent, 1),
    }


def collect_disk() -> list:
    disks = []
    for part in psutil.disk_partitions():
        try:
            u = psutil.disk_usage(part.mountpoint)
            disks.append({
                "mount": part.mountpoint,
                "total": u.total,
                "total_gb": round(u.total / (1024 ** 3), 1),
                "used_gb": round(u.used / (1024 ** 3), 1),
                "free_gb": round(u.free / (1024 ** 3), 1),
                "percent": round(u.percent, 1),
            })
        except PermissionError:
            continue
    return disks


def collect_hostname() -> str:
    return socket.gethostname()


def collect_os() -> str:
    return f"{platform.system()} {platform.release()} ({platform.machine()})"


# ── HTTP helpers ───────────────────────────────────────────────────────────
def _request(method: str, url: str, json_data=None, headers=None, timeout=10):
    h = {"Content-Type": "application/json"}
    if headers:
        h.update(headers)
    try:
        resp = requests.request(method, url, json=json_data, headers=h, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.RequestException as e:
        logger.error("HTTP error %s %s: %s", method, url, e)
        return None
    except json.JSONDecodeError:
        return None


# ── Agent client ───────────────────────────────────────────────────────────
class AgentClient:
    def __init__(self, cfg: Dict[str, Any]):
        self.cfg = cfg
        self.base = cfg["backend_url"].rstrip("/")
        self.token = cfg["agent_bootstrap_token"]
        self.agent_id = ""
        self.credential = ""
        self.registered = False
        self._stop_event = asyncio.Event()

        # 初始化 CPU 基线：首次调用 cpu_percent(interval=None) 返回 0.0，
        # 需要一次预热调用建立采样基线，后续每次调用返回与上一次的对比值
        psutil.cpu_percent(interval=None)

    def _make_agent_id(self) -> str:
        prefix = self.cfg.get("agent_id_prefix", "kylin-win")
        hostname = collect_hostname()
        return f"{prefix}-{hostname}".lower()

    def register(self) -> bool:
        """Register this agent with the backend via POST /agent/register."""
        agent_id = self._make_agent_id()
        logger.info("Registering agent: %s", agent_id)

        payload = {
            "agent_id": agent_id,
            "hostname": collect_hostname(),
            "ip_address": "",
            "os_version": collect_os(),
            "kernel_version": platform.version(),
            "agent_version": "2.4.9",
            "cpu_cores": psutil.cpu_count(logical=True),
            "total_memory": psutil.virtual_memory().total,
            "disk_total": sum(d["total"] for d in collect_disk()),
            "tags": ["windows", "desktop"],
        }
        result = _request(
            "POST",
            f"{self.base}/api/v1/agent/register",
            json_data=payload,
            headers={"X-Agent-Bootstrap-Token": self.token},
        )
        if result and result.get("code") == 200:
            data = result.get("data", {})
            self.agent_id = agent_id
            self.credential = data.get("credential", "")
            self.registered = True
            logger.info("Registered OK. credential=%s", self.credential[:20] + "...")
            return True
        logger.error("Registration failed: %s", result)
        return False

    def send_heartbeat(self) -> bool:
        """Send a single heartbeat. Returns True on success."""
        if not self.registered or not self.credential:
            logger.warning("Not registered yet, skipping heartbeat")
            return False

        cpu = collect_cpu()
        mem = collect_memory()
        disks = collect_disk()

        payload = {
            "agentId": self.agent_id,
            "ts": int(time.time()),
            "version": "2.4.9",
            "cpu": {"usage": cpu["usage"], "cores": cpu["count"]},
            "memory": {"total": mem["total"], "total_mb": mem["total_mb"], "used_mb": mem["used_mb"], "percent": mem["percent"]},
            "disk": disks,
            "processes": {"total": len(psutil.pids())},
            "load_avg": [],
            "hostname": collect_hostname(),
        }

        result = _request(
            "POST",
            f"{self.base}/api/v1/agent/heartbeat",
            json_data=payload,
            headers={"X-Agent-Token": self.credential},
        )
        if result and result.get("code") == 200:
            logger.debug("Heartbeat OK: %s", json.dumps(result.get("data", {}), ensure_ascii=False))
            return True
        logger.warning("Heartbeat failed: %s", result)
        return False

    async def run(self):
        """Main loop: register → heartbeat every N seconds."""
        interval = self.cfg.get("heartbeat_interval", 10)
        logger.info("Agent starting (interval=%ds, backend=%s)", interval, self.base)

        # Register
        if not self.register():
            logger.warning("Registration failed — will retry on each heartbeat cycle")

        while not self._stop_event.is_set():
            try:
                if not self.registered:
                    self.register()

                self.send_heartbeat()

                logger.info(
                    "Status: %s | CPU: %.1f%% | Mem: %.1f%%",
                    "registered" if self.registered else "registering",
                    collect_cpu()["usage"],
                    collect_memory()["percent"],
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("Heartbeat loop error: %s", e)

            # Sleep in chunks so we can stop quickly
            for _ in range(interval * 10):
                if self._stop_event.is_set():
                    return
                await asyncio.sleep(0.1)

    def stop(self):
        self._stop_event.set()


# ── Entry point ────────────────────────────────────────────────────────────
def main():
    cfg = load_config()
    client = AgentClient(cfg)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(client.run())
    except KeyboardInterrupt:
        logger.info("Interrupted")
    finally:
        client.stop()
        loop.run_until_complete(asyncio.gather(*asyncio.all_tasks(loop), return_exceptions=True))
        loop.close()


if __name__ == "__main__":
    main()
