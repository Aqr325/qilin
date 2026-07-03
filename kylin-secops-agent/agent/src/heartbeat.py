"""
Heartbeat collector — system resource acquisition and status reporting.

Collects CPU, memory, disk, process count, and load average every 5-12 seconds
(variable interval). Pushes immediately when CPU > 90% or disk < 5%.

On Kylin OS, also collects Kylin-specific security subsystem metrics
(kysec, SELinux, auditd, firewall, security baseline).

Uses psutil for all basic data acquisition — no privileged syscalls.
Kylin-specific collection uses subprocess commands (requires root).
"""

import asyncio
import random
import time
from typing import Any, Dict, List, Optional, Callable

import psutil

from src import __version__
from src.logger import get_logger

logger = get_logger("heartbeat")


class HeartbeatCollector:
    """Periodic system resource collector with anomaly detection."""

    def __init__(self, config, on_heartbeat: Callable, on_alert: Optional[Callable] = None):
        """
        Args:
            config: AgentConfig instance.
            on_heartbeat: Async callback invoked with heartbeat payload dict.
            on_alert: Optional async callback for immediate anomaly alerts.
        """
        self._config = config
        self._on_heartbeat = on_heartbeat
        self._on_alert = on_alert
        self._running = False
        self._interval_min = config.get("heartbeat", "interval_min") or 5
        self._interval_max = config.get("heartbeat", "interval_max") or 12
        self._cpu_threshold = config.get("heartbeat", "cpu_threshold") or 90.0
        self._disk_threshold = config.get("heartbeat", "disk_threshold") or 5.0
        self._agent_id = config.agent_id

        # Kylin-specific monitoring
        self._kylin_info_cache: Optional[Dict[str, Any]] = None
        self._kylin_cache_ts: float = 0
        self._kylin_cache_ttl: float = 60.0  # refresh Kylin info every 60s

    # ═══════════════════════════════════════════════════════════════════
    # Data acquisition
    # ═══════════════════════════════════════════════════════════════════

    @staticmethod
    def collect_cpu() -> Dict[str, Any]:
        """Collect CPU metrics."""
        return {
            "usage": psutil.cpu_percent(interval=0.5),
            "count": psutil.cpu_count(logical=True),
            "physical_count": psutil.cpu_count(logical=False),
        }

    @staticmethod
    def collect_memory() -> Dict[str, Any]:
        """Collect memory metrics (in MB)."""
        mem = psutil.virtual_memory()
        return {
            "total_mb": round(mem.total / (1024 * 1024), 1),
            "used_mb": round(mem.used / (1024 * 1024), 1),
            "available_mb": round(mem.available / (1024 * 1024), 1),
            "percent": round(mem.percent, 1),
        }

    @staticmethod
    def collect_disk() -> List[Dict[str, Any]]:
        """Collect per-mount-point disk metrics (in GB)."""
        disks = []
        for part in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(part.mountpoint)
                disks.append({
                    "mount": part.mountpoint,
                    "fstype": part.fstype,
                    "total_gb": round(usage.total / (1024 ** 3), 1),
                    "used_gb": round(usage.used / (1024 ** 3), 1),
                    "free_gb": round(usage.free / (1024 ** 3), 1),
                    "percent": round(usage.percent, 1),
                })
            except PermissionError:
                # Some mounts may not be accessible (e.g. snap)
                continue
        return disks

    @staticmethod
    def collect_processes() -> Dict[str, Any]:
        """Collect process count."""
        return {
            "total": len(psutil.pids()),
            # running count is approximate via iterating
        }

    @staticmethod
    def collect_load_avg() -> List[float]:
        """Collect load average (1, 5, 15 min)."""
        avg = psutil.getloadavg()
        return [round(v, 2) for v in avg]

    def collect_all(self) -> Dict[str, Any]:
        """Collect all system metrics in one shot."""
        data = {
            "cpu": self.collect_cpu(),
            "memory": self.collect_memory(),
            "disk": self.collect_disk(),
            "processes": self.collect_processes(),
            "load_avg": self.collect_load_avg(),
            "version": __version__,
        }

        # Collect Kylin-specific info (cached, refreshed every 60s)
        kylin_info = self._collect_kylin_info()
        if kylin_info:
            data["kylin"] = kylin_info

        return data

    # ═══════════════════════════════════════════════════════════════════
    # Kylin OS-specific data collection
    # ═══════════════════════════════════════════════════════════════════

    def _collect_kylin_info(self) -> Dict[str, Any]:
        """Collect Kylin OS-specific security subsystem metrics.

        Uses cached result (refreshes every _kylin_cache_ttl seconds)
        to avoid excessive subprocess calls on every heartbeat.
        """
        now = time.time()
        if self._kylin_info_cache is not None and (now - self._kylin_cache_ts) < self._kylin_cache_ttl:
            return self._kylin_info_cache

        try:
            from src.kylin_monitor import (
                is_kylin_os,
                collect_kylin_system_info,
                detect_kylin_version,
                check_security_baseline,
            )

            if not is_kylin_os():
                self._kylin_info_cache = None
                return {}

            # 在缓存刷新间隔内，分批次采集不同数据
            # 减少单次调用的开销
            kylin_info = {
                "os": detect_kylin_version(),
                "baseline": check_security_baseline(),
            }

            # 完整采集每 N 次心跳
            heartbeat_count = getattr(self, "_heartbeat_count", 0)
            if heartbeat_count % 6 == 0:  # ~每 30-60 秒一次完整采集
                full_info = collect_kylin_system_info()
                kylin_info.update({
                    "kysec": full_info.get("kysec", {}),
                    "selinux": full_info.get("selinux", {}),
                    "audit": full_info.get("audit", {}),
                    "network": full_info.get("network", {}),
                    "packages": full_info.get("packages", {}),
                    "kernel_modules": full_info.get("kernel_modules", {}),
                })

            self._heartbeat_count = heartbeat_count + 1
            self._kylin_info_cache = kylin_info
            self._kylin_cache_ts = now
            return kylin_info

        except ImportError:
            # kylin_monitor not available
            return {}
        except Exception as exc:
            logger.warning("Kylin info collection error: %s", exc)
            return {}

    # ═══════════════════════════════════════════════════════════════════
    # Anomaly detection
    # ═══════════════════════════════════════════════════════════════════

    def _check_anomalies(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Check for anomalous conditions requiring immediate push."""
        alerts = []

        cpu_percent = data.get("cpu", {}).get("usage", 0)
        if cpu_percent > self._cpu_threshold:
            alerts.append({
                "type": "cpu_overload",
                "severity": "critical",
                "value": cpu_percent,
                "threshold": self._cpu_threshold,
                "message": f"CPU usage {cpu_percent}% exceeds threshold {self._cpu_threshold}%",
            })

        for disk in data.get("disk", []):
            free_pct = 100 - disk.get("percent", 0)
            if free_pct < self._disk_threshold:
                alerts.append({
                    "type": "disk_low_space",
                    "severity": "critical",
                    "mount": disk["mount"],
                    "free_pct": round(free_pct, 1),
                    "threshold": self._disk_threshold,
                    "message": (
                        f"Disk {disk['mount']} free space {free_pct:.1f}% "
                        f"below threshold {self._disk_threshold}%"
                    ),
                })

        # ── Kylin-specific anomaly checks ─────────────────────────
        kylin = data.get("kylin", {})
        if kylin:
            # kysec 安全内核关闭告警
            kysec = kylin.get("kysec", {})
            if kysec and not kysec.get("enabled"):
                alerts.append({
                    "type": "kysec_disabled",
                    "severity": "high",
                    "message": "Kylin kysec security module is disabled — "
                               "system is running without mandatory access control",
                })

            # SELinux 关闭告警
            selinux = kylin.get("selinux", {})
            if selinux and not selinux.get("enabled"):
                alerts.append({
                    "type": "selinux_disabled",
                    "severity": "medium",
                    "message": "SELinux is disabled — system lacks MAC protection",
                })

            # 安全基线评分偏低
            baseline = kylin.get("baseline", {})
            score = baseline.get("compliance_score", 100)
            if score < 50:
                alerts.append({
                    "type": "low_compliance_score",
                    "severity": "high",
                    "value": score,
                    "message": (
                        f"Security baseline compliance score is {score}% — "
                        f"system hardening recommended"
                    ),
                })
            elif score < 70:
                alerts.append({
                    "type": "low_compliance_score",
                    "severity": "medium",
                    "value": score,
                    "message": f"Security baseline compliance score {score}% — below target",
                })

        return alerts

    # ═══════════════════════════════════════════════════════════════════
    # Main loop
    # ═══════════════════════════════════════════════════════════════════

    async def run(self):
        """Run the heartbeat collection loop."""
        self._running = True
        logger.info(
            "Heartbeat collector started (interval %d-%d sec, cpu_threshold=%.0f%%, "
            "disk_threshold=%.0f%%)",
            self._interval_min, self._interval_max,
            self._cpu_threshold, self._disk_threshold,
        )

        while self._running:
            try:
                data = self.collect_all()
                ts = time.time()

                payload = {
                    "type": "heartbeat",
                    "agent_id": self._agent_id,
                    "ts": ts,
                    "data": data,
                }

                # Check anomalies (push immediately regardless of interval)
                anomalies = self._check_anomalies(data)
                if anomalies:
                    logger.warning("Anomalies detected: %s", anomalies)
                    if self._on_alert:
                        await self._on_alert({
                            "type": "anomaly",
                            "agent_id": self._agent_id,
                            "ts": ts,
                            "data": anomalies,
                        })
                    # Still send heartbeat with anomaly flag
                    payload["anomaly"] = True

                await self._on_heartbeat(payload)

                # Variable sleep: random interval between min and max
                interval = random.uniform(self._interval_min, self._interval_max)
                await asyncio.sleep(interval)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Heartbeat collection error: %s", exc)
                await asyncio.sleep(self._interval_min)

    def stop(self):
        self._running = False
